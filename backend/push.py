"""Web Push Notifications via VAPID.

Generates a VAPID keypair on first run and stores it in the `push_config` collection,
so the same keys survive restarts. Exposes:
- GET /api/push/vapid-public-key    (raw url-safe b64, browser applicationServerKey)
- POST /api/push/subscribe          (save browser PushSubscription for current user)
- POST /api/push/unsubscribe        (remove)
- send_push(user_id, title, body, url)   → async helper any module can call
"""
import asyncio
import base64
import json
import logging
import os
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from cryptography.hazmat.primitives.asymmetric.ec import generate_private_key, SECP256R1
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption,
)
from pywebpush import webpush, WebPushException

from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/push", tags=["push"])

_VAPID_CACHE: Dict[str, Any] = {"loaded": False}


async def _load_or_create_vapid() -> Dict[str, str]:
    """Return {public_b64, private_pem, subject}. Cached in-process."""
    if _VAPID_CACHE.get("loaded"):
        return _VAPID_CACHE
    row = await db.push_config.find_one({"id": "vapid"})
    if row and row.get("private_pem") and row.get("public_b64"):
        _VAPID_CACHE.update({
            "loaded": True,
            "public_b64": row["public_b64"],
            "private_pem": row["private_pem"],
            "subject": row.get("subject", "mailto:hello@artcore.app"),
        })
        return _VAPID_CACHE
    # Generate fresh keypair
    priv = generate_private_key(SECP256R1())
    private_pem = priv.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
    ).decode()
    raw_pub = priv.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_b64 = base64.urlsafe_b64encode(raw_pub).rstrip(b"=").decode()
    subject = os.environ.get("VAPID_SUBJECT", "mailto:hello@artcore.app")
    await db.push_config.update_one(
        {"id": "vapid"},
        {"$set": {"id": "vapid", "public_b64": public_b64, "private_pem": private_pem, "subject": subject, "created_at": now_iso()}},
        upsert=True,
    )
    _VAPID_CACHE.update({"loaded": True, "public_b64": public_b64, "private_pem": private_pem, "subject": subject})
    log.info("Generated new VAPID keypair for web push")
    return _VAPID_CACHE


@router.get("/vapid-public-key")
async def vapid_public_key():
    cfg = await _load_or_create_vapid()
    return {"public_key": cfg["public_b64"]}


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeReq(BaseModel):
    endpoint: str
    keys: PushKeys
    expirationTime: Optional[float] = None


@router.post("/subscribe")
async def subscribe(req: SubscribeReq, me: dict = Depends(get_current_user)):
    """Idempotent — one row per (user, endpoint)."""
    doc = {
        "id": new_id(),
        "user_id": me["id"],
        "endpoint": req.endpoint,
        "keys": {"p256dh": req.keys.p256dh, "auth": req.keys.auth},
        "created_at": now_iso(),
    }
    await db.push_subscriptions.update_one(
        {"user_id": me["id"], "endpoint": req.endpoint},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True}


class UnsubReq(BaseModel):
    endpoint: str


@router.post("/unsubscribe")
async def unsubscribe(req: UnsubReq, me: dict = Depends(get_current_user)):
    r = await db.push_subscriptions.delete_many({"user_id": me["id"], "endpoint": req.endpoint})
    return {"removed": r.deleted_count}


@router.get("/subscriptions/mine")
async def my_subscriptions(me: dict = Depends(get_current_user)):
    cursor = db.push_subscriptions.find({"user_id": me["id"]}, {"endpoint": 1, "created_at": 1})
    rows = [strip_mongo(r) for r in await cursor.to_list(50)]
    return {"count": len(rows), "subscriptions": rows}


class TestPushReq(BaseModel):
    title: Optional[str] = "Art Core"
    body: Optional[str] = "Push notifications are live 🎨"
    url: Optional[str] = "/notifications"


@router.post("/test")
async def push_test(req: TestPushReq, me: dict = Depends(get_current_user)):
    """Fire a push to *me* — useful for verifying the subscription round-trip."""
    n = await send_push(me["id"], req.title, req.body, req.url)
    return {"delivered": n}


def _send_one(subject: str, private_pem: str, sub: Dict[str, Any], payload: str) -> bool:
    """Blocking call — run inside a thread pool via send_push()."""
    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
            data=payload,
            vapid_private_key=private_pem,
            vapid_claims={"sub": subject},
            ttl=60,
        )
        return True
    except WebPushException as e:
        log.warning("web push failed: %s", e)
        return False


async def send_push(user_id: str, title: str, body: str, url: str = "/") -> int:
    """Fan out a push to every subscription the user has. Deletes 404/410 endpoints."""
    cfg = await _load_or_create_vapid()
    cursor = db.push_subscriptions.find({"user_id": user_id})
    subs = await cursor.to_list(50)
    if not subs:
        return 0
    payload = json.dumps({"title": title, "body": body, "url": url})
    delivered = 0
    dead: list = []
    loop = asyncio.get_event_loop()
    for s in subs:
        try:
            ok = await loop.run_in_executor(
                None, _send_one, cfg["subject"], cfg["private_pem"], s, payload
            )
            if ok:
                delivered += 1
            else:
                dead.append(s["endpoint"])
        except Exception as e:  # noqa
            log.warning("push exception: %s", e)
            dead.append(s["endpoint"])
    if dead:
        await db.push_subscriptions.delete_many({"user_id": user_id, "endpoint": {"$in": dead}})
    return delivered
