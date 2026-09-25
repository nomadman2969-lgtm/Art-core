"""Artist referrals: invite an artist → when they make their first sale, the referrer's next sale is fee-free and both earn a badge."""
import os
import secrets
import string
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from db import db, new_id, now_iso
from auth import get_current_user

router = APIRouter(prefix="/api/referrals", tags=["referrals"])
APP_URL = os.environ.get("PUBLIC_APP_URL", "https://artcorestudio.net")
ALPHABET = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"


async def ensure_code(user: dict) -> str:
    if user.get("referral_code"):
        return user["referral_code"]
    for _ in range(10):
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        if not await db.users.find_one({"referral_code": code}):
            await db.users.update_one({"id": user["id"]}, {"$set": {"referral_code": code}})
            return code
    raise HTTPException(500, "Could not generate code")


async def attach_referrer(new_user: dict, code: Optional[str]) -> None:
    """Called at registration — only artists can refer, only artists count as referred."""
    if not code or new_user.get("role") != "artist":
        return
    ref = await db.users.find_one({"referral_code": code.strip().upper(), "role": {"$in": ["artist", "admin"]}})
    if not ref or ref["id"] == new_user["id"]:
        return
    await db.users.update_one({"id": new_user["id"]}, {"$set": {"referred_by": ref["id"], "referred_at": now_iso()}})
    await db.notifications.insert_one({"id": new_id(), "user_id": ref["id"], "kind": "referral_joined", "from_user_id": new_user["id"],
                                       "from_user_name": new_user["name"], "read": False, "created_at": now_iso()})


async def on_first_sale(seller_id: str) -> None:
    """Fire once when a referred artist completes their first paid sale → referrer gets a fee-free sale credit; both get badges."""
    seller = await db.users.find_one({"id": seller_id})
    if not seller or not seller.get("referred_by") or seller.get("referral_converted_at"):
        return
    await db.users.update_one({"id": seller_id}, {"$set": {"referral_converted_at": now_iso()}})
    await db.users.update_one({"id": seller["referred_by"]}, {"$inc": {"fee_free_sales": 1, "referral_conversions": 1}})
    await db.notifications.insert_one({"id": new_id(), "user_id": seller["referred_by"], "kind": "referral_reward", "from_user_id": seller_id,
                                       "from_user_name": seller["name"], "read": False, "created_at": now_iso()})
    await db.notifications.insert_one({"id": new_id(), "user_id": seller_id, "kind": "referral_badge", "read": False, "created_at": now_iso()})


async def consume_fee_free_sale(seller_id: str) -> None:
    await db.users.update_one({"id": seller_id, "fee_free_sales": {"$gt": 0}}, {"$inc": {"fee_free_sales": -1, "fee_free_used": 1}})


@router.get("/me")
async def my_referrals(user: dict = Depends(get_current_user)):
    if user["role"] not in ("artist", "admin"):
        raise HTTPException(403, "Artists only")
    code = await ensure_code(user)
    invitees = await db.users.find({"referred_by": user["id"]}, {"id": 1, "name": 1, "avatar": 1, "created_at": 1, "referral_converted_at": 1}).sort("created_at", -1).to_list(200)
    return {
        "code": code,
        "link": f"{APP_URL}/register?role=artist&ref={code}",
        "invited": len(invitees),
        "converted": sum(1 for i in invitees if i.get("referral_converted_at")),
        "fee_free_sales": int(user.get("fee_free_sales") or 0),
        "fee_free_used": int(user.get("fee_free_used") or 0),
        "invitees": [{"id": i["id"], "name": i["name"], "avatar": i.get("avatar"), "joined_at": i.get("created_at"), "first_sale_at": i.get("referral_converted_at")} for i in invitees],
    }


@router.get("/check/{code}")
async def check_code(code: str):
    ref = await db.users.find_one({"referral_code": code.strip().upper()}, {"name": 1, "avatar": 1})
    if not ref:
        raise HTTPException(404, "Unknown code")
    return {"valid": True, "referrer_name": ref["name"], "referrer_avatar": ref.get("avatar")}
