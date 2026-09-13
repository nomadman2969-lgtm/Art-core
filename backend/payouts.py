"""Depop-style payout release: funds stay on the platform until delivery is confirmed (or a safety hold lapses).

Release rules (per artist_payout on an order):
  - buyer confirms delivery/pickup  → release 2 days later (Pro: immediately)
  - no confirmation                 → release 10 business days after sale (Pro: 5)
A sweep transfers due payouts to connected Stripe accounts; unconnected artists fall back to manual settlement ("pending").
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from db import db, new_id, now_iso

HOLD_BUSINESS_DAYS = 10
PRO_HOLD_BUSINESS_DAYS = 5
DELIVERY_DELAY_DAYS = 2


def _now():
    return datetime.now(timezone.utc)


def add_business_days(start: datetime, days: int) -> datetime:
    d = start
    while days > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days -= 1
    return d


def _is_pro(user: Optional[dict]) -> bool:
    from auth import _pro_active
    return bool(user and _pro_active(user))


async def initial_release_at(artist_id: str) -> str:
    artist = await db.users.find_one({"id": artist_id})
    return add_business_days(_now(), PRO_HOLD_BUSINESS_DAYS if _is_pro(artist) else HOLD_BUSINESS_DAYS).isoformat()


async def hold_payouts(payouts: list) -> list:
    """Mark fresh payouts as held with a safety-hold release date."""
    out = []
    for p in payouts:
        if p.get("status") in ("pending", "held"):
            p = {**p, "status": "held", "release_at": await initial_release_at(p["artist_id"]), "hold_reason": "awaiting_delivery"}
        out.append(p)
    return out


async def release_on_delivery(order: dict) -> list:
    """Buyer confirmed delivery/pickup → bring release_at forward (2 days; Pro: now)."""
    payouts = order.get("artist_payouts", [])
    for p in payouts:
        if p.get("status") != "held":
            continue
        artist = await db.users.find_one({"id": p["artist_id"]})
        delay = 0 if _is_pro(artist) else DELIVERY_DELAY_DAYS
        p["release_at"] = (_now() + timedelta(days=delay)).isoformat()
        p["hold_reason"] = "delivered"
    return payouts


def freeze_payouts(order: dict, reason: str) -> list:
    """Dispute / not-received → stop the release clock until an admin resolves."""
    payouts = order.get("artist_payouts", [])
    for p in payouts:
        if p.get("status") == "held":
            p["frozen_release_at"] = p.get("release_at")
            p["release_at"] = None
            p["hold_reason"] = reason
    return payouts


async def unfreeze_payouts(order: dict) -> list:
    """Dispute rejected → treat as delivered and restart the 2-day (Pro: now) countdown."""
    payouts = order.get("artist_payouts", [])
    for p in payouts:
        if p.get("status") != "held" or p.get("release_at"):
            continue
        artist = await db.users.find_one({"id": p["artist_id"]})
        delay = 0 if _is_pro(artist) else DELIVERY_DELAY_DAYS
        p["release_at"] = (_now() + timedelta(days=delay)).isoformat()
        p["hold_reason"] = "dispute_rejected"
        p.pop("frozen_release_at", None)
    return payouts


async def release_due_payouts() -> int:
    """Sweep: transfer every held payout whose release_at has passed."""
    from connect import transfer_manual
    now = _now().isoformat()
    released = 0
    cursor = db.orders.find({"refunded": {"$ne": True}, "artist_payouts": {"$elemMatch": {"status": "held", "release_at": {"$lte": now}}}})
    async for o in cursor:
        payouts = o.get("artist_payouts", [])
        changed = False
        for p in payouts:
            if p.get("status") != "held" or (p.get("release_at") or "9") > now:
                continue
            try:
                result = await transfer_manual(p["artist_id"], p["net"], source_reference=f"order:{o['id']}", description=f"Art Core payout · order {o['id'][:8]}")
            except Exception as e:
                result = None
                p["transfer_error"] = str(e)[:200]
            if result:
                p["status"] = "transferred"
                p["stripe_transfer_id"] = result["transfer_id"]
            else:
                p["status"] = "pending"  # no Connect account yet → admin settles manually
            p["released_at"] = now_iso()
            changed = True
            released += 1
            await db.notifications.insert_one({"id": new_id(), "user_id": p["artist_id"], "kind": "payout_released",
                                               "amount": p["net"], "order_id": o["id"], "read": False, "created_at": now_iso()})
        if changed:
            await db.orders.update_one({"id": o["id"]}, {"$set": {"artist_payouts": payouts}})
    return released


async def upcoming_for_artist(artist_id: str) -> list:
    """Held payouts with their scheduled release — powers 'Next payout' in the Payouts tab."""
    rows = []
    async for o in db.orders.find({"artist_payouts": {"$elemMatch": {"artist_id": artist_id, "status": "held"}}, "refunded": {"$ne": True}}).sort("created_at", -1):
        for p in o.get("artist_payouts", []):
            if p.get("artist_id") == artist_id and p.get("status") == "held":
                rows.append({"order_id": o["id"], "net": p["net"], "gross": p.get("gross"), "release_at": p.get("release_at"),
                             "hold_reason": p.get("hold_reason", "awaiting_delivery"), "fulfillment": (o.get("fulfillment") or {}).get("status", "pending"),
                             "created_at": o.get("created_at")})
    rows.sort(key=lambda r: r["release_at"] or "9")
    return rows
