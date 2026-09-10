"""Optional two-factor auth: TOTP (authenticator app) or email OTP, with recovery codes.

Login flow: /auth/login returns {"requires_2fa": true, "challenge_token": ...} when enabled;
client then POSTs /auth/2fa/verify-login with the 6-digit code (or a recovery code) to get the JWT.
"""
import os
import hmac
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
import pyotp
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso
from auth import get_current_user, verify_password, make_token, public_user, JWT_SECRET, JWT_ALG

router = APIRouter(prefix="/api/auth/2fa", tags=["2fa"])
APP_NAME = os.environ.get("APP_NAME", "Art Core")
CHALLENGE_MINUTES = 5
EMAIL_CODE_MINUTES = 10


def _hash(code: str) -> str:
    return hashlib.sha256(code.strip().upper().replace("-", "").encode()).hexdigest()


def make_challenge_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "typ": "2fa", "exp": datetime.now(timezone.utc) + timedelta(minutes=CHALLENGE_MINUTES)}, JWT_SECRET, algorithm=JWT_ALG)


def _decode_challenge(token: str) -> str:
    try:
        p = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Challenge expired — sign in again")
    if p.get("typ") != "2fa":
        raise HTTPException(401, "Invalid challenge")
    return p["sub"]


async def send_email_code(user: dict) -> None:
    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "twofa_email_code_hash": _hash(code),
        "twofa_email_code_exp": (datetime.now(timezone.utc) + timedelta(minutes=EMAIL_CODE_MINUTES)).isoformat(),
    }})
    try:
        from emails import send_email, otp_email_html
        import asyncio
        asyncio.create_task(send_email(user["email"], f"{code} is your {APP_NAME} code", otp_email_html(user.get("name") or "there", code, EMAIL_CODE_MINUTES)))
    except Exception:
        pass


def _check_totp(secret: str, code: str) -> bool:
    return bool(secret) and pyotp.TOTP(secret).verify(code.strip().replace(" ", ""), valid_window=1)


async def _check_email_code(user: dict, code: str) -> bool:
    h, exp = user.get("twofa_email_code_hash"), user.get("twofa_email_code_exp")
    if not h or not exp or datetime.fromisoformat(exp) < datetime.now(timezone.utc):
        return False
    if not hmac.compare_digest(h, _hash(code)):
        return False
    await db.users.update_one({"id": user["id"]}, {"$unset": {"twofa_email_code_hash": "", "twofa_email_code_exp": ""}})
    return True


async def _check_recovery(user: dict, code: str) -> bool:
    codes = user.get("twofa_recovery_hashes") or []
    h = _hash(code)
    if h not in codes:
        return False
    await db.users.update_one({"id": user["id"]}, {"$pull": {"twofa_recovery_hashes": h}})
    return True


async def verify_any(user: dict, code: str) -> bool:
    method = user.get("twofa_method")
    if method == "totp" and _check_totp(user.get("twofa_secret", ""), code):
        return True
    if method == "email" and await _check_email_code(user, code):
        return True
    return await _check_recovery(user, code)


def _new_recovery_codes():
    codes = [f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}" for _ in range(8)]
    return codes, [_hash(c) for c in codes]


# ---------- Status / setup ----------
@router.get("/status")
async def status(user: dict = Depends(get_current_user)):
    return {
        "enabled": bool(user.get("twofa_enabled")),
        "method": user.get("twofa_method"),
        "recovery_codes_left": len(user.get("twofa_recovery_hashes") or []),
    }


class SetupReq(BaseModel):
    method: str = Field(pattern="^(totp|email)$")


@router.post("/setup")
async def setup(req: SetupReq, user: dict = Depends(get_current_user)):
    """Start enrolment. TOTP → returns otpauth URI + QR; email → sends a code."""
    if user.get("twofa_enabled"):
        raise HTTPException(400, "2FA is already enabled — disable it first to change method")
    if req.method == "totp":
        secret = pyotp.random_base32()
        await db.users.update_one({"id": user["id"]}, {"$set": {"twofa_pending_secret": secret, "twofa_pending_method": "totp"}})
        uri = pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name=APP_NAME)
        qr = None
        try:
            import qrcode, io, base64
            buf = io.BytesIO()
            qrcode.make(uri, box_size=8, border=2).save(buf, format="PNG")
            qr = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass
        return {"method": "totp", "secret": secret, "otpauth_uri": uri, "qr_image": qr}
    await db.users.update_one({"id": user["id"]}, {"$set": {"twofa_pending_method": "email"}})
    await send_email_code(user)
    return {"method": "email", "sent_to": user["email"]}


class CodeReq(BaseModel):
    code: str = Field(min_length=4, max_length=16)


@router.post("/enable")
async def enable(req: CodeReq, user: dict = Depends(get_current_user)):
    """Confirm enrolment with a valid code; returns one-time recovery codes."""
    method = user.get("twofa_pending_method")
    if not method:
        raise HTTPException(400, "Start setup first")
    if method == "totp":
        ok = _check_totp(user.get("twofa_pending_secret", ""), req.code)
    else:
        ok = await _check_email_code(user, req.code)
    if not ok:
        raise HTTPException(400, "That code didn't work — try again")
    codes, hashes = _new_recovery_codes()
    updates = {"twofa_enabled": True, "twofa_method": method, "twofa_recovery_hashes": hashes, "twofa_enabled_at": now_iso()}
    if method == "totp":
        updates["twofa_secret"] = user["twofa_pending_secret"]
    await db.users.update_one({"id": user["id"]}, {"$set": updates, "$unset": {"twofa_pending_secret": "", "twofa_pending_method": ""}})
    return {"enabled": True, "method": method, "recovery_codes": codes}


class DisableReq(BaseModel):
    password: str
    code: str = Field(min_length=4, max_length=16)


@router.post("/disable")
async def disable(req: DisableReq, user: dict = Depends(get_current_user)):
    if not user.get("twofa_enabled"):
        raise HTTPException(400, "2FA is not enabled")
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Wrong password")
    if not await verify_any(user, req.code):
        raise HTTPException(400, "That code didn't work")
    await db.users.update_one({"id": user["id"]}, {"$unset": {
        "twofa_enabled": "", "twofa_method": "", "twofa_secret": "", "twofa_recovery_hashes": "",
        "twofa_email_code_hash": "", "twofa_email_code_exp": "", "twofa_enabled_at": "",
    }})
    return {"enabled": False}


@router.post("/recovery-codes")
async def regen_recovery(req: CodeReq, user: dict = Depends(get_current_user)):
    if not user.get("twofa_enabled"):
        raise HTTPException(400, "2FA is not enabled")
    if not await verify_any(user, req.code):
        raise HTTPException(400, "That code didn't work")
    codes, hashes = _new_recovery_codes()
    await db.users.update_one({"id": user["id"]}, {"$set": {"twofa_recovery_hashes": hashes}})
    return {"recovery_codes": codes}


# ---------- Login challenge ----------
class ChallengeReq(BaseModel):
    challenge_token: str


@router.post("/resend")
async def resend(req: ChallengeReq):
    uid = _decode_challenge(req.challenge_token)
    user = await db.users.find_one({"id": uid})
    if not user or user.get("twofa_method") != "email":
        raise HTTPException(400, "Email codes are not enabled for this account")
    await send_email_code(user)
    return {"sent": True}


TRUSTED_DAYS = 30


async def is_trusted_device(user: dict, device_token: Optional[str]) -> bool:
    if not device_token:
        return False
    h = _hash(device_token)
    now = datetime.now(timezone.utc).isoformat()
    for d in user.get("trusted_devices") or []:
        if hmac.compare_digest(d.get("hash", ""), h) and d.get("expires_at", "") > now:
            await db.users.update_one({"id": user["id"], "trusted_devices.id": d["id"]}, {"$set": {"trusted_devices.$.last_used_at": now}})
            return True
    return False


class VerifyLoginReq(BaseModel):
    challenge_token: str
    code: str = Field(min_length=4, max_length=16)
    remember_device: bool = False
    device_label: Optional[str] = Field(default=None, max_length=120)


@router.post("/verify-login")
async def verify_login(req: VerifyLoginReq):
    uid = _decode_challenge(req.challenge_token)
    user = await db.users.find_one({"id": uid})
    if not user or not user.get("twofa_enabled"):
        raise HTTPException(401, "Invalid challenge")
    fails = int(user.get("twofa_fail_count") or 0)
    if fails >= 8:
        raise HTTPException(429, "Too many attempts — sign in again in a few minutes")
    if not await verify_any(user, req.code):
        await db.users.update_one({"id": uid}, {"$inc": {"twofa_fail_count": 1}})
        raise HTTPException(401, "Wrong code")
    await db.users.update_one({"id": uid}, {"$unset": {"twofa_fail_count": ""}})
    out = {"token": make_token(user["id"], user["role"]), "user": public_user(user)}
    if req.remember_device:
        raw = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        device = {"id": new_id(), "hash": _hash(raw), "label": (req.device_label or "This device")[:120],
                  "created_at": now.isoformat(), "last_used_at": now.isoformat(), "expires_at": (now + timedelta(days=TRUSTED_DAYS)).isoformat()}
        await db.users.update_one({"id": uid}, {"$push": {"trusted_devices": {"$each": [device], "$slice": -10}}})
        out["device_token"] = raw
        out["device_expires_at"] = device["expires_at"]
    return out


@router.get("/devices")
async def list_devices(user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    return [{k: d[k] for k in ("id", "label", "created_at", "last_used_at", "expires_at")} for d in user.get("trusted_devices") or [] if d.get("expires_at", "") > now]


@router.delete("/devices/{device_id}")
async def revoke_device(device_id: str, user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$pull": {"trusted_devices": {"id": device_id}}})
    return {"ok": True}


@router.delete("/devices")
async def revoke_all_devices(user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"trusted_devices": []}})
    return {"ok": True}
