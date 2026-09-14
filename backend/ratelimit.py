"""Mongo-backed sliding-window rate limits (survive restarts, no Redis)."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from db import db

LOGIN_IP_LIMIT, LOGIN_IP_WINDOW = 30, 15 * 60
LOGIN_EMAIL_LIMIT, LOGIN_EMAIL_WINDOW = 10, 15 * 60
OTP_RESEND_LIMIT, OTP_RESEND_WINDOW = 3, 10 * 60
TWOFA_LOCK_MINUTES = 15


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def ensure_indexes():
    await db.rate_limits.create_index("expires_at", expireAfterSeconds=0)
    await db.rate_limits.create_index("key", unique=True)


async def check(key: str, limit: int, window: int):
    """Raise 429 (with Retry-After) when `key` has >= limit hits inside the window."""
    now = datetime.now(timezone.utc)
    doc = await db.rate_limits.find_one({"key": key})
    hits = [h for h in (doc or {}).get("hits", []) if h > (now - timedelta(seconds=window)).isoformat()]
    if len(hits) >= limit:
        retry = int((datetime.fromisoformat(hits[0]) + timedelta(seconds=window) - now).total_seconds()) + 1
        raise HTTPException(429, "Too many attempts — try again later", headers={"Retry-After": str(max(retry, 1))})


async def hit(key: str, window: int):
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(seconds=window)).isoformat()
    doc = await db.rate_limits.find_one({"key": key})
    hits = [h for h in (doc or {}).get("hits", []) if h > cutoff] + [now.isoformat()]
    await db.rate_limits.update_one({"key": key}, {"$set": {"hits": hits, "expires_at": now + timedelta(seconds=window)}}, upsert=True)


async def clear(key: str):
    await db.rate_limits.delete_one({"key": key})
