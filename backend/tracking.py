"""Live carrier tracking via EasyPost (USPS/UPS/FedEx/DHL + 100 carriers).

Degrades gracefully: without EASYPOST_API_KEY orders stay in manual mode (seller taps "Tracking shows delivered"
or the 7-day estimate kicks in). With a key, a Tracker is created at ship time; `tracker.updated` webhooks
(and a 30-min polling fallback) flip the order to carrier_delivered automatically.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pymongo.errors import DuplicateKeyError
from db import db, now_iso, strip_mongo
from auth import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["tracking"])

CARRIER_MAP = {
    "usps": "USPS", "ups": "UPS", "fedex": "FedEx", "fed_ex": "FedEx", "fed ex": "FedEx",
    "dhl": "DHLExpress", "dhlexpress": "DHLExpress", "dhl express": "DHLExpress", "dhl ecommerce": "DHLEcommerce",
    "canadapost": "CanadaPost", "canada post": "CanadaPost", "royalmail": "RoyalMail", "royal mail": "RoyalMail",
    "ontrac": "OnTrac", "lasership": "LaserShip", "purolator": "Purolator", "australiapost": "AustraliaPost",
}
TERMINAL = {"delivered", "return_to_sender", "failure", "cancelled", "error"}
POLL_EVERY_MIN = 30


def api_key() -> Optional[str]:
    return os.environ.get("EASYPOST_API_KEY") or None


def webhook_secret() -> Optional[str]:
    return os.environ.get("EASYPOST_WEBHOOK_SECRET") or None


def enabled() -> bool:
    return bool(api_key())


def _client():
    import easypost
    return easypost.EasyPostClient(api_key())


def normalize_carrier(raw: str) -> Optional[str]:
    return CARRIER_MAP.get((raw or "").strip().lower().replace("-", ""))


def _tracker_snapshot(t: dict) -> dict:
    details = t.get("tracking_details") or []
    events = [{"status": d.get("status"), "message": d.get("message"), "at": d.get("datetime"),
               "city": (d.get("tracking_location") or {}).get("city"), "state": (d.get("tracking_location") or {}).get("state")}
              for d in details[-8:]]
    return {"tracker_id": t.get("id"), "tracking_status": t.get("status"), "tracking_status_detail": t.get("status_detail"),
            "carrier_canonical": t.get("carrier"), "est_delivery": t.get("est_delivery_date"), "tracking_events": events,
            "tracking_url": t.get("public_url"), "tracking_polled_at": now_iso()}


async def _apply_tracker(order: dict, t: dict, source: str):
    snap = _tracker_snapshot(t)
    await db.orders.update_one({"id": order["id"]}, {"$set": {f"fulfillment.{k}": v for k, v in snap.items()}})
    if snap["tracking_status"] == "delivered" and (order.get("fulfillment") or {}).get("status") == "shipped":
        from delivery import mark_carrier_delivered
        fresh = await db.orders.find_one({"id": order["id"]})
        await mark_carrier_delivered(fresh, f"carrier:{source}")
        log.info("Order %s auto-flagged delivered via EasyPost (%s)", order["id"], source)


async def start_tracking(order_id: str, carrier: str, tracking: str) -> Optional[dict]:
    """Create an EasyPost Tracker at ship time. Never raises — manual mode remains the fallback."""
    if not enabled():
        return None
    canonical = normalize_carrier(carrier)
    try:
        kwargs = {"tracking_code": tracking.strip()}
        if canonical:
            kwargs["carrier"] = canonical
        tracker = await asyncio.to_thread(lambda: _client().tracker.create(**kwargs))
        t = tracker.to_dict() if hasattr(tracker, "to_dict") else dict(tracker)
        order = await db.orders.find_one({"id": order_id})
        await db.orders.update_one({"id": order_id}, {"$set": {"fulfillment.tracking_source": "easypost"}})
        await _apply_tracker(order, t, "create")
        return t
    except Exception as e:
        log.warning("EasyPost tracker create failed for order %s: %s", order_id, e)
        await db.orders.update_one({"id": order_id}, {"$set": {"fulfillment.tracking_source": "manual", "fulfillment.tracking_error": str(e)[:200]}})
        return None


async def poll_active_trackers() -> int:
    """Fallback for missed webhooks: refresh shipped orders with a tracker every POLL_EVERY_MIN."""
    if not enabled():
        return 0
    stale = (datetime.now(timezone.utc) - timedelta(minutes=POLL_EVERY_MIN)).isoformat()
    q = {"fulfillment.status": "shipped", "fulfillment.tracker_id": {"$exists": True, "$ne": None}, "refunded": {"$ne": True},
         "$or": [{"fulfillment.tracking_polled_at": {"$lte": stale}}, {"fulfillment.tracking_polled_at": {"$exists": False}}]}
    n = 0
    for o in await db.orders.find(q).to_list(100):
        try:
            tracker = await asyncio.to_thread(lambda: _client().tracker.retrieve(o["fulfillment"]["tracker_id"]))
            await _apply_tracker(o, tracker.to_dict() if hasattr(tracker, "to_dict") else dict(tracker), "poll")
            n += 1
        except Exception as e:
            log.warning("EasyPost poll failed for order %s: %s", o["id"], e)
            await db.orders.update_one({"id": o["id"]}, {"$set": {"fulfillment.tracking_polled_at": now_iso()}})
    return n


# ---------- routes ----------
@router.get("/tracking/config")
async def tracking_config():
    return {"live_tracking": enabled(), "webhook_configured": bool(webhook_secret()), "carriers": sorted(set(CARRIER_MAP.values()))}


@router.get("/orders/{oid}/tracking")
async def order_tracking(oid: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    is_party = o.get("buyer_id") == user["id"] or any(p["artist_id"] == user["id"] for p in o.get("artist_payouts", []))
    if not (is_party or user["role"] == "admin"):
        raise HTTPException(403, "Not yours")
    f = o.get("fulfillment") or {}
    if enabled() and f.get("tracker_id") and f.get("status") == "shipped":
        try:
            tracker = await asyncio.to_thread(lambda: _client().tracker.retrieve(f["tracker_id"]))
            await _apply_tracker(o, tracker.to_dict() if hasattr(tracker, "to_dict") else dict(tracker), "manual_refresh")
            f = (await db.orders.find_one({"id": oid})).get("fulfillment") or {}
        except Exception as e:
            log.warning("EasyPost refresh failed: %s", e)
    return {"live_tracking": enabled(), **{k: f.get(k) for k in ("status", "carrier", "tracking", "tracking_source", "tracker_id", "tracking_status",
                                                                  "tracking_status_detail", "est_delivery", "tracking_events", "tracking_url", "tracking_polled_at", "carrier_canonical")}}


@router.post("/tracking/easypost/webhook")
async def easypost_webhook(request: Request):
    secret = webhook_secret()
    if not secret:
        raise HTTPException(503, "EasyPost webhooks are not configured")
    raw = await request.body()
    try:
        from easypost.util import validate_webhook
        event = validate_webhook(raw, {"X-Hmac-Signature": request.headers.get("x-hmac-signature", "")}, secret)
    except Exception:
        raise HTTPException(401, "invalid webhook signature")
    if event.get("object") != "Event" or not str(event.get("description", "")).startswith("tracker."):
        return {"ignored": True}
    event_id = event.get("id")
    if not event_id:
        raise HTTPException(400, "missing event id")
    t = event.get("result") or {}
    order = await db.orders.find_one({"fulfillment.tracker_id": t.get("id")}) if t.get("id") else None
    if not order and t.get("tracking_code"):
        order = await db.orders.find_one({"fulfillment.tracking": t["tracking_code"], "fulfillment.status": {"$in": ["shipped", "carrier_delivered"]}})
    if not order:
        return {"accepted": True, "matched": False}
    try:
        await db.webhook_events.insert_one({"event_id": event_id, "provider": "easypost", "received_at": now_iso()})
    except DuplicateKeyError:
        return {"duplicate": True}
    await _apply_tracker(strip_mongo(order), t, "webhook")
    return {"accepted": True, "matched": True}


async def ensure_indexes():
    await db.webhook_events.create_index("event_id", unique=True)
