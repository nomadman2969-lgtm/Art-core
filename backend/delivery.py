"""Delivery confirmation (anti-chargeback / INR guard).

Fulfillment pipeline: pending → shipped → carrier_delivered → delivered | not_received
  - seller (or transit-estimate sweep) marks carrier_delivered → buyer is forced to answer
  - buyer "received"      → delivered, payout countdown starts
  - buyer "not received"  → not_received, dispute auto-opened with tracking proof, payout frozen
  - no answer in 3 days   → auto-confirmed, payout countdown starts
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user

router = APIRouter(prefix="/api", tags=["delivery"])

CONFIRM_WINDOW_DAYS = 3
ESTIMATED_TRANSIT_DAYS = 7
APP_URL = os.environ.get("PUBLIC_APP_URL", "https://artcorestudio.net")


def _now():
    return datetime.now(timezone.utc)


def _status(o: dict) -> str:
    return (o.get("fulfillment") or {}).get("status", "pending")


async def _notify(user_id: str, kind: str, **extra):
    await db.notifications.insert_one({"id": new_id(), "user_id": user_id, "kind": kind, "read": False, "created_at": now_iso(), **extra})


async def _push(user_id: str, title: str, body: str, url: str, kind: str):
    try:
        from push import send_push
        await send_push(user_id, title, body, url, kind=kind)
    except Exception:
        pass


async def _order_summary(o: dict) -> dict:
    items = []
    for it in o.get("items", []):
        art = await db.artworks.find_one({"id": it["artwork_id"]})
        artist = await db.users.find_one({"id": it["artist_id"]})
        items.append({"artwork_id": it["artwork_id"], "title": art["title"] if art else "Artwork",
                      "image": (art.get("images") or [None])[0] if art else None,
                      "artist_name": artist["name"] if artist else None, "price": it.get("price")})
    f = o.get("fulfillment") or {}
    return {"id": o["id"], "total": o.get("total"), "created_at": o.get("created_at"), "items": items,
            "fulfillment": {"status": f.get("status"), "carrier": f.get("carrier"), "tracking": f.get("tracking"),
                            "shipped_at": f.get("shipped_at"), "carrier_delivered_at": f.get("carrier_delivered_at"),
                            "carrier_delivered_source": f.get("carrier_delivered_source"), "confirm_deadline": f.get("confirm_deadline")}}


async def mark_carrier_delivered(o: dict, source: str, by: Optional[str] = None) -> dict:
    """Tracking shows delivered → start the buyer confirmation window."""
    deadline = (_now() + timedelta(days=CONFIRM_WINDOW_DAYS)).isoformat()
    await db.orders.update_one({"id": o["id"]}, {"$set": {
        "fulfillment.status": "carrier_delivered", "fulfillment.carrier_delivered_at": now_iso(),
        "fulfillment.carrier_delivered_source": source, "fulfillment.carrier_delivered_by": by,
        "fulfillment.confirm_deadline": deadline,
    }})
    buyer = await db.users.find_one({"id": o.get("buyer_id")}) if o.get("buyer_id") else None
    if buyer:
        f = o.get("fulfillment") or {}
        await _notify(buyer["id"], "order_delivered_confirm", order_id=o["id"], carrier=f.get("carrier"), tracking=f.get("tracking"), confirm_deadline=deadline)
        await _push(buyer["id"], "Did your order arrive?", f"Tracking shows order #{o['id'][:8]} was delivered. Tap to confirm you received it.", f"/orders/{o['id']}", "order_delivered_confirm")
        if buyer.get("email"):
            from emails import send_email, delivery_confirm_html
            await send_email(buyer["email"], "Did your Art Core order arrive?", delivery_confirm_html(buyer["name"], o["id"], f.get("carrier"), f.get("tracking"), f"{APP_URL}/orders/{o['id']}", CONFIRM_WINDOW_DAYS))
    fresh = await db.orders.find_one({"id": o["id"]})
    return strip_mongo(fresh)


async def confirm_received(o: dict, how: str, by: Optional[str] = None) -> dict:
    """Buyer confirmed (or auto-confirm) → delivered + payout countdown."""
    from payouts import release_on_delivery
    payouts = await release_on_delivery(o)
    await db.orders.update_one({"id": o["id"]}, {"$set": {
        "fulfillment.status": "delivered", "fulfillment.delivered_at": now_iso(),
        "fulfillment.confirmed_how": how, "fulfillment.confirmed_by": by, "artist_payouts": payouts,
    }})
    for p in payouts:
        if p.get("status") == "held":
            await _notify(p["artist_id"], "order_received_confirmed" if how == "buyer" else "order_auto_confirmed",
                          order_id=o["id"], artwork_id=p.get("artwork_id"), amount=p["net"], release_at=p.get("release_at"))
    if how == "auto" and o.get("buyer_id"):
        await _notify(o["buyer_id"], "order_auto_confirmed", order_id=o["id"])
    fresh = await db.orders.find_one({"id": o["id"]})
    return strip_mongo(fresh)


async def report_not_received(o: dict, user: dict) -> dict:
    """Buyer says the item never arrived → freeze payout + auto-open a dispute with tracking proof."""
    from payouts import freeze_payouts
    f = o.get("fulfillment") or {}
    payouts = freeze_payouts(o, "not_received")
    await db.orders.update_one({"id": o["id"]}, {"$set": {
        "fulfillment.status": "not_received", "fulfillment.not_received_at": now_iso(), "artist_payouts": payouts,
    }})
    existing = await db.disputes.find_one({"order_id": o["id"], "status": {"$in": ["open", "under_review"]}})
    if not existing:
        seller_id = (o.get("artist_payouts") or [{}])[0].get("artist_id")
        d = {
            "id": new_id(), "order_id": o["id"], "buyer_id": user["id"], "seller_id": seller_id,
            "reason": "not_received",
            "description": f"Buyer reported the item was not received after tracking showed delivered. Tracking proof: {f.get('carrier') or '—'} {f.get('tracking') or '—'} (carrier delivered {f.get('carrier_delivered_at') or 'n/a'}, source: {f.get('carrier_delivered_source') or 'n/a'}).",
            "images": [], "tracking_proof": {"carrier": f.get("carrier"), "tracking": f.get("tracking"), "shipped_at": f.get("shipped_at"),
                                             "carrier_delivered_at": f.get("carrier_delivered_at"), "source": f.get("carrier_delivered_source")},
            "auto_opened": True, "status": "open", "resolution": None, "refund_amount": None, "admin_note": None,
            "history": [{"kind": "opened", "by": user["id"], "at": now_iso(), "via": "not_received_prompt"}],
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        await db.disputes.insert_one(d)
        await db.orders.update_one({"id": o["id"]}, {"$set": {"dispute_status": "open", "dispute_id": d["id"]}})
        if seller_id:
            await _notify(seller_id, "order_not_received", dispute_id=d["id"], order_id=o["id"], reason="not_received")
            await _push(seller_id, "Buyer reports item not received", f"Order #{o['id'][:8]} — payout frozen while we review the tracking.", f"/orders/{o['id']}", "order_not_received")
        async for admin in db.users.find({"role": "admin"}):
            await _notify(admin["id"], "dispute_opened", dispute_id=d["id"], order_id=o["id"], reason="not_received", from_user_name=user["name"])
    fresh = await db.orders.find_one({"id": o["id"]})
    return strip_mongo(fresh)


# ---------- routes ----------
@router.get("/orders/confirmations/pending")
async def pending_confirmations(user: dict = Depends(get_current_user)):
    """Orders where tracking says delivered and the buyer hasn't answered yet — drives the un-dismissable prompt."""
    cursor = db.orders.find({"buyer_id": user["id"], "fulfillment.status": "carrier_delivered", "refunded": {"$ne": True}}).sort("fulfillment.carrier_delivered_at", 1)
    return [await _order_summary(o) for o in await cursor.to_list(50)]


@router.post("/orders/{oid}/carrier-delivered")
async def seller_carrier_delivered(oid: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    is_seller = any(p["artist_id"] == user["id"] for p in o.get("artist_payouts", []))
    if not is_seller and user["role"] != "admin":
        raise HTTPException(403, "Not the seller")
    if _status(o) != "shipped":
        raise HTTPException(400, f"Order must be shipped first — status is {_status(o)}")
    if not (o.get("fulfillment") or {}).get("tracking"):
        raise HTTPException(400, "Tracking number is required")
    from orders import _enrich_order
    return await _enrich_order(await mark_carrier_delivered(o, "seller" if user["role"] != "admin" else "admin", by=user["id"]))


@router.post("/orders/{oid}/confirm-received")
async def buyer_confirm_received(oid: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    if o.get("buyer_id") != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not the buyer")
    if _status(o) not in ("shipped", "carrier_delivered"):
        raise HTTPException(400, f"Cannot confirm — status is {_status(o)}")
    from orders import _enrich_order
    return await _enrich_order(await confirm_received(o, "buyer", by=user["id"]))


@router.post("/orders/{oid}/not-received")
async def buyer_not_received(oid: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    if o.get("buyer_id") != user["id"]:
        raise HTTPException(403, "Not the buyer")
    if _status(o) not in ("shipped", "carrier_delivered"):
        raise HTTPException(400, f"Cannot report — status is {_status(o)}")
    if o.get("refunded"):
        raise HTTPException(400, "Order already refunded")
    from orders import _enrich_order
    return await _enrich_order(await report_not_received(o, user))


# ---------- sweeps (called from the server loop) ----------
async def sweep_delivery_confirmations() -> dict:
    now = _now()
    estimated = 0
    cutoff = (now - timedelta(days=ESTIMATED_TRANSIT_DAYS)).isoformat()
    for o in await db.orders.find({"fulfillment.status": "shipped", "fulfillment.shipped_at": {"$lte": cutoff}, "refunded": {"$ne": True}}).to_list(200):
        await mark_carrier_delivered(o, "estimated")
        estimated += 1
    auto = 0
    for o in await db.orders.find({"fulfillment.status": "carrier_delivered", "fulfillment.confirm_deadline": {"$lte": now.isoformat()}, "refunded": {"$ne": True}}).to_list(200):
        await confirm_received(o, "auto")
        auto += 1
    return {"estimated_delivered": estimated, "auto_confirmed": auto}
