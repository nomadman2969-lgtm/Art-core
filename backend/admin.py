"""Admin endpoints: settings, AOTW curation, orders, mentorship, featured artworks, refunds."""
import os
import stripe
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import require_role, public_user

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- settings ---
class SettingsUpdate(BaseModel):
    commission_percent: Optional[float] = None
    upload_fee: Optional[float] = None
    currency: Optional[str] = None


async def _get_settings():
    s = await db.settings.find_one({"id": "global"})
    if not s:
        default = {"id": "global", "commission_percent": 4.0, "upload_fee": 5.0, "currency": "usd", "aotw_artwork_id": None, "created_at": now_iso()}
        await db.settings.insert_one(default)
        s = await db.settings.find_one({"id": "global"})
    return strip_mongo(s)


@router.get("/settings")
async def get_settings(user=Depends(require_role("admin"))):
    return await _get_settings()


@router.patch("/settings")
async def update_settings(req: SettingsUpdate, user=Depends(require_role("admin"))):
    updates = {k: v for k, v in req.model_dump(exclude_none=True).items()}
    if updates:
        await db.settings.update_one({"id": "global"}, {"$set": updates}, upsert=True)
    return await _get_settings()


# --- Featured artworks ---
class FeaturedReq(BaseModel):
    artwork_id: str
    featured: bool


@router.post("/featured")
async def set_featured(req: FeaturedReq, user=Depends(require_role("admin"))):
    art = await db.artworks.find_one({"id": req.artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    await db.artworks.update_one({"id": req.artwork_id}, {"$set": {"featured": req.featured}})
    return {"ok": True}


# --- Art of the Week ---
class AOTWReq(BaseModel):
    artwork_id: str


@router.post("/aotw")
async def set_aotw(req: AOTWReq, user=Depends(require_role("admin"))):
    art = await db.artworks.find_one({"id": req.artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    await db.artworks.update_many({"aotw": True}, {"$set": {"aotw": False}})
    await db.artworks.update_one({"id": req.artwork_id}, {"$set": {"aotw": True, "aotw_selected_at": now_iso()}})
    await db.settings.update_one({"id": "global"}, {"$set": {"aotw_artwork_id": req.artwork_id}}, upsert=True)
    return {"ok": True}


@router.get("/aotw/submissions")
async def aotw_submissions(user=Depends(require_role("admin"))):
    cursor = db.artworks.find({"aotw_submitted": True, "status": "live"}).sort("created_at", -1)
    out = []
    for a in await cursor.to_list(200):
        a = strip_mongo(a)
        artist = await db.users.find_one({"id": a["artist_id"]})
        if artist:
            a["artist"] = {"id": artist["id"], "name": artist["name"]}
        out.append(a)
    return out


# --- Orders ---
@router.get("/orders")
async def all_orders(user=Depends(require_role("admin"))):
    cursor = db.orders.find({}).sort("created_at", -1)
    orders = [strip_mongo(o) for o in await cursor.to_list(500)]
    return orders


@router.get("/artists")
async def all_artists(user=Depends(require_role("admin"))):
    cursor = db.users.find({"role": "artist"}).sort("created_at", -1)
    out = []
    for u in await cursor.to_list(500):
        u = strip_mongo(u)
        out.append(public_user(u))
    return out


# --- Mentorship ---
class MentorshipFlag(BaseModel):
    artist_id: str
    note: str


@router.post("/mentorship")
async def flag_mentorship(req: MentorshipFlag, user=Depends(require_role("admin"))):
    entry = {
        "id": new_id(),
        "artist_id": req.artist_id,
        "note": req.note,
        "resolved": False,
        "created_at": now_iso(),
    }
    await db.mentorship.insert_one(entry)
    return strip_mongo(entry)


@router.get("/mentorship")
async def list_mentorship(user=Depends(require_role("admin"))):
    cursor = db.mentorship.find({}).sort("created_at", -1)
    out = []
    for m in await cursor.to_list(500):
        m = strip_mongo(m)
        artist = await db.users.find_one({"id": m["artist_id"]})
        if artist:
            m["artist"] = {"id": artist["id"], "name": artist["name"], "email": artist["email"]}
        out.append(m)
    return out


@router.patch("/mentorship/{item_id}/resolve")
async def resolve_mentorship(item_id: str, user=Depends(require_role("admin"))):
    await db.mentorship.update_one({"id": item_id}, {"$set": {"resolved": True}})
    return {"ok": True}


# --- Dashboard stats ---
@router.get("/stats")
async def stats(user=Depends(require_role("admin"))):
    total_orders = await db.orders.count_documents({})
    orders = await db.orders.find({}).to_list(2000)
    revenue = sum(o.get("total", 0) for o in orders)
    platform_take = sum(o.get("platform_take", 0) for o in orders)
    artists = await db.users.count_documents({"role": "artist"})
    buyers = await db.users.count_documents({"role": "buyer"})
    artworks_live = await db.artworks.count_documents({"status": "live"})
    return {
        "total_orders": total_orders,
        "revenue": round(revenue, 2),
        "platform_take": round(platform_take, 2),
        "artists": artists,
        "buyers": buyers,
        "artworks_live": artworks_live,
    }


# --- Newsletter ---
class NewsletterReq(BaseModel):
    email: str


newsletter_router = APIRouter(prefix="/api", tags=["newsletter"])


@newsletter_router.post("/newsletter")
async def newsletter_signup(req: NewsletterReq):
    existing = await db.newsletter.find_one({"email": req.email.lower()})
    if existing:
        return {"ok": True, "already": True}
    await db.newsletter.insert_one({"id": new_id(), "email": req.email.lower(), "created_at": now_iso()})
    return {"ok": True}


@router.get("/newsletter")
async def list_newsletter(user=Depends(require_role("admin"))):
    cursor = db.newsletter.find({}).sort("created_at", -1)
    return [strip_mongo(n) for n in await cursor.to_list(1000)]


# ---------- Refund Console ----------
class RefundReq(BaseModel):
    amount: Optional[float] = None
    reason: Optional[str] = None
    reverse_payouts: bool = True


async def _refund_stripe_transaction(session_id: str, amount: Optional[float], reason: Optional[str]):
    """Refund via the PaymentIntent that this Checkout Session created. Returns (refund_id, refunded_amount)."""
    try:
        s = stripe.checkout.Session.retrieve(session_id)
        pi = s.payment_intent
        if not pi:
            raise HTTPException(400, "No PaymentIntent — payment may still be pending")
        kwargs = {"payment_intent": pi}
        if amount is not None:
            kwargs["amount"] = int(round(amount * 100))
        if reason in ("duplicate", "fraudulent", "requested_by_customer"):
            kwargs["reason"] = reason
        kwargs["reverse_transfer"] = True
        kwargs["refund_application_fee"] = True
        r = stripe.Refund.create(**kwargs)
        return r.id, (r.amount or 0) / 100.0
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Stripe refund failed: {e.user_message or str(e)[:200]}")


@router.get("/refundable")
async def list_refundable(user=Depends(require_role("admin"))):
    out = []
    orders = await db.orders.find({"refunded": {"$ne": True}}).sort("created_at", -1).to_list(200)
    for o in orders:
        o = strip_mongo(o)
        out.append({
            "kind": "order",
            "id": o["id"],
            "session_id": o.get("session_id"),
            "buyer_id": o.get("buyer_id"),
            "amount": o.get("total"),
            "currency": o.get("currency", "usd"),
            "source": o.get("source", "buyer_order"),
            "created_at": o.get("created_at"),
            "fulfillment_status": (o.get("fulfillment") or {}).get("status"),
            "artist_payouts": o.get("artist_payouts", []),
        })
    commissions = await db.commissions.find({"paid": True, "refunded": {"$ne": True}}).sort("paid_at", -1).to_list(200)
    for c in commissions:
        c = strip_mongo(c)
        tx = await db.payment_transactions.find_one({"commission_id": c["id"], "kind": "commission_payment", "payment_status": "paid"})
        deposit_tx = await db.payment_transactions.find_one({"commission_id": c["id"], "kind": "commission_deposit", "payment_status": "paid"})
        out.append({
            "kind": "commission",
            "id": c["id"],
            "subject": c.get("subject"),
            "buyer_id": c.get("buyer_id"),
            "artist_id": c.get("artist_id"),
            "amount": float(c.get("counter_amount") or c.get("budget") or 0),
            "currency": "usd",
            "created_at": c.get("paid_at") or c.get("updated_at"),
            "session_id": tx.get("session_id") if tx else None,
            "deposit_session_id": deposit_tx.get("session_id") if deposit_tx else None,
        })
    return out


@router.post("/orders/{oid}/refund")
async def refund_order(oid: str, req: RefundReq, user=Depends(require_role("admin"))):
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Order not found")
    if o.get("refunded"):
        raise HTTPException(400, "Already refunded")
    session_id = o.get("session_id")
    if not session_id:
        raise HTTPException(400, "No Stripe session on this order")
    refund_id, refunded = await _refund_stripe_transaction(session_id, req.amount, req.reason)
    payouts = o.get("artist_payouts", [])
    if req.reverse_payouts:
        for p in payouts:
            if p.get("status") in ("auto_transferred", "transferred"):
                p["status"] = "reversed"
            elif p.get("status") == "released":
                p["status"] = "clawback_needed"
            elif p.get("status") == "pending":
                p["status"] = "cancelled"
    is_full = (req.amount is None) or (abs(refunded - float(o["total"])) < 0.01)
    await db.orders.update_one({"id": oid}, {"$set": {
        "refunded": is_full,
        "refund_amount": refunded,
        "refund_reason": req.reason,
        "refunded_at": now_iso(),
        "stripe_refund_id": refund_id,
        "artist_payouts": payouts,
    }})
    if is_full:
        for it in o.get("items", []):
            await db.artworks.update_one({"id": it["artwork_id"], "status": "sold"}, {"$set": {"status": "live"}})
    if o.get("buyer_id"):
        await db.notifications.insert_one({
            "id": new_id(), "user_id": o["buyer_id"], "kind": "order_refunded",
            "order_id": oid, "amount": refunded, "read": False, "created_at": now_iso(),
        })
    for p in payouts:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": p["artist_id"], "kind": "payout_reversed",
            "order_id": oid, "amount": p.get("net"), "read": False, "created_at": now_iso(),
        })
    return {"refunded": refunded, "refund_id": refund_id, "full": is_full}


@router.post("/commissions/{cid}/refund")
async def refund_commission(cid: str, req: RefundReq, user=Depends(require_role("admin"))):
    c = await db.commissions.find_one({"id": cid})
    if not c:
        raise HTTPException(404, "Commission not found")
    if c.get("refunded"):
        raise HTTPException(400, "Already refunded")
    balance_tx = await db.payment_transactions.find_one({"commission_id": cid, "kind": "commission_payment", "payment_status": "paid"})
    deposit_tx = await db.payment_transactions.find_one({"commission_id": cid, "kind": "commission_deposit", "payment_status": "paid"})
    if not balance_tx and not deposit_tx:
        raise HTTPException(400, "No paid transactions on this commission")
    total_refunded = 0.0
    refund_ids = []
    remaining = req.amount
    if balance_tx:
        amt = remaining if remaining is not None else None
        rid, r_amt = await _refund_stripe_transaction(balance_tx["session_id"], amt, req.reason)
        refund_ids.append(rid); total_refunded += r_amt
        if remaining is not None:
            remaining -= r_amt
    if deposit_tx and (remaining is None or remaining > 0.001):
        amt = remaining if remaining is not None else None
        rid, r_amt = await _refund_stripe_transaction(deposit_tx["session_id"], amt, req.reason)
        refund_ids.append(rid); total_refunded += r_amt
    total = float(c.get("counter_amount") or c.get("budget") or 0)
    is_full = abs(total_refunded - total) < 0.01
    await db.commissions.update_one({"id": cid}, {"$set": {
        "refunded": is_full,
        "refund_amount": total_refunded,
        "refund_reason": req.reason,
        "refunded_at": now_iso(),
        "stripe_refund_ids": refund_ids,
        "status": "refunded" if is_full else c["status"],
    }})
    await db.notifications.insert_one({
        "id": new_id(), "user_id": c["buyer_id"], "kind": "commission_refunded",
        "commission_id": cid, "amount": total_refunded, "read": False, "created_at": now_iso(),
    })
    await db.notifications.insert_one({
        "id": new_id(), "user_id": c["artist_id"], "kind": "commission_refunded",
        "commission_id": cid, "amount": total_refunded, "read": False, "created_at": now_iso(),
    })
    return {"refunded": total_refunded, "refund_ids": refund_ids, "full": is_full}
