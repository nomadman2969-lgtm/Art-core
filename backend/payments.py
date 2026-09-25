"""Stripe checkout for buyers + upload fee for artists."""
import os
import stripe
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, get_optional_user, require_role

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

router = APIRouter(prefix="/api", tags=["payments"])


async def get_settings() -> dict:
    s = await db.settings.find_one({"id": "global"})
    if not s:
        default = {
            "id": "global",
            "commission_percent": 4.0,
            "upload_fee": 5.0,
            "currency": "usd",
            "deposit_percent": 50.0,
            "processing_percent": 2.9,
            "processing_fixed": 0.30,
            "waiver_enabled": True,
            "waiver_days": 30,
            "waiver_max_sales": 5,
            "founding_enabled": True,
            "founding_rate": 4.0,
            "founding_cap": 500,
            "aotw_artwork_id": None,
            "created_at": now_iso(),
        }
        await db.settings.insert_one(default)
        return default
    return strip_mongo(s)


def split_amount(gross: float, settings: dict) -> dict:
    """Seller-pays-processing split: platform keeps commission, seller nets gross - commission - card processing."""
    gross = float(gross)
    platform_take = round(gross * float(settings["commission_percent"]) / 100.0, 2)
    processing_fee = round(gross * float(settings.get("processing_percent", 2.9)) / 100.0 + float(settings.get("processing_fixed", 0.30)), 2) if gross > 0 else 0.0
    net = round(max(0.0, gross - platform_take - processing_fee), 2)
    return {"platform_take": platform_take, "processing_fee": processing_fee, "net": net}


# ---------- Buyer checkout ----------
class CheckoutItem(BaseModel):
    artwork_id: str
    quantity: int = 1


class BuyerCheckoutReq(BaseModel):
    items: List[CheckoutItem] = Field(min_length=1)
    origin_url: str


@router.post("/payments/checkout")
async def buyer_checkout(req: BuyerCheckoutReq, user: Optional[dict] = Depends(get_optional_user)):
    settings = await get_settings()
    currency = settings["currency"]
    line_items = []
    tx_items = []
    total = 0.0
    for it in req.items:
        art = await db.artworks.find_one({"id": it.artwork_id})
        if not art:
            raise HTTPException(400, f"Artwork not found: {it.artwork_id}")
        if art["status"] != "live":
            raise HTTPException(400, f"Not available: {art['title']}")
        amount_cents = int(round(float(art["price"]) * 100))
        line_items.append({
            "price_data": {
                "currency": currency,
                "product_data": {
                    "name": art["title"],
                    "description": (art.get("description") or "")[:400],
                },
                "unit_amount": amount_cents,
            },
            "quantity": it.quantity,
        })
        tx_items.append({
            "artwork_id": art["id"],
            "artist_id": art["artist_id"],
            "price": float(art["price"]),
            "quantity": it.quantity,
        })
        total += float(art["price"]) * it.quantity

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        shipping_address_collection={"allowed_countries": ["US", "CA", "GB", "AU", "DE", "FR", "IT", "ES", "NL", "IE", "SE", "NO", "DK", "FI", "JP", "MX", "BR"]},
        customer_email=user["email"] if user else None,
        metadata={
            "kind": "buyer_order",
            "user_id": user["id"] if user else "",
        },
    )
    await db.payment_transactions.insert_one({
        "id": new_id(),
        "session_id": session.id,
        "kind": "buyer_order",
        "user_id": user["id"] if user else None,
        "items": tx_items,
        "amount": total,
        "currency": currency,
        "status": "initiated",
        "payment_status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


# ---------- Artist upload fee ----------
class UploadFeeReq(BaseModel):
    artwork_id: str
    origin_url: str


@router.post("/payments/upload-fee")
async def upload_fee_checkout(req: UploadFeeReq, user: dict = Depends(require_role("artist", "admin"))):
    settings = await get_settings()
    fee = float(settings["upload_fee"])
    art = await db.artworks.find_one({"id": req.artwork_id})
    if not art or art["artist_id"] != user["id"]:
        raise HTTPException(404, "Artwork not found")
    if art["status"] == "live":
        raise HTTPException(400, "Already live")
    if fee <= 0:
        # Free — go live immediately
        await db.artworks.update_one({"id": req.artwork_id}, {"$set": {"status": "live"}})
        _art = await db.artworks.find_one({"id": req.artwork_id})
        if _art:
            from engage import notify_followers_soon
            notify_followers_soon(_art["artist_id"], "followed_new_artwork", f"New work from {user['name']}", _art["title"], f"/artwork/{_art['id']}", artwork_id=_art["id"])
        return {"checkout_url": None, "session_id": None, "free": True}
    amount_cents = int(round(fee * 100))
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings["currency"],
                "product_data": {"name": f"Listing fee: {art['title']}"},
                "unit_amount": amount_cents,
            },
            "quantity": 1,
        }],
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        customer_email=user["email"],
        metadata={"kind": "upload_fee", "artwork_id": req.artwork_id, "user_id": user["id"]},
    )
    await db.payment_transactions.insert_one({
        "id": new_id(),
        "session_id": session.id,
        "kind": "upload_fee",
        "user_id": user["id"],
        "artwork_id": req.artwork_id,
        "amount": fee,
        "currency": settings["currency"],
        "status": "initiated",
        "payment_status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


# ---------- Auction winner payment ----------
class AuctionPayReq(BaseModel):
    origin_url: str


@router.post("/payments/auctions/{auction_id}/pay")
async def pay_auction(auction_id: str, req: AuctionPayReq, user: dict = Depends(get_current_user)):
    au = await db.auctions.find_one({"id": auction_id})
    if not au:
        raise HTTPException(404, "Auction not found")
    if au["status"] != "ended":
        raise HTTPException(400, "Auction not ended")
    if au.get("winner_id") != user["id"]:
        raise HTTPException(403, "Not the winner")
    if au.get("paid"):
        raise HTTPException(400, "Already paid")
    # Enforce 48h payment deadline
    from datetime import datetime as _dt, timezone as _tz
    deadline = au.get("payment_deadline")
    if deadline:
        try:
            dl = _dt.fromisoformat(deadline.replace("Z", "+00:00"))
            if _dt.now(_tz.utc) > dl:
                raise HTTPException(400, "Payment window expired — auction passed to next bidder")
        except ValueError:
            pass
    amount = float(au.get("final_price") or au.get("current_bid") or 0)
    if amount <= 0:
        raise HTTPException(400, "Invalid amount")
    art = await db.artworks.find_one({"id": au["artwork_id"]})
    settings = await get_settings()
    from connect import build_transfer_options
    transfer_kwargs = await build_transfer_options(au["seller_id"], amount)
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings["currency"],
                "product_data": {"name": f"Auction win: {art['title'] if art else 'Artwork'}"},
                "unit_amount": int(round(amount * 100)),
            },
            "quantity": 1,
        }],
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        shipping_address_collection={"allowed_countries": ["US", "CA", "GB", "AU", "DE", "FR", "IT", "ES", "NL", "IE", "SE", "NO", "DK", "FI", "JP", "MX", "BR"]},
        customer_email=user["email"],
        metadata={"kind": "auction_win", "auction_id": auction_id, "user_id": user["id"]},
        **transfer_kwargs,
    )
    await db.payment_transactions.insert_one({
        "id": new_id(), "session_id": session.id,
        "kind": "auction_win", "user_id": user["id"],
        "auction_id": auction_id, "artwork_id": au["artwork_id"],
        "seller_id": au["seller_id"],
        "amount": amount, "currency": settings["currency"],
        "status": "initiated", "payment_status": "pending",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


# ---------- Commission payment (deposit + balance escrow) ----------
class CommissionPayReq(BaseModel):
    origin_url: str


@router.post("/payments/commissions/{commission_id}/deposit")
async def pay_commission_deposit(commission_id: str, req: CommissionPayReq, user: dict = Depends(get_current_user)):
    c = await db.commissions.find_one({"id": commission_id})
    if not c:
        raise HTTPException(404, "Commission not found")
    if c["buyer_id"] != user["id"]:
        raise HTTPException(403, "Not your commission")
    if c["status"] != "in_progress":
        raise HTTPException(400, "Deposit only after artist accepts")
    if c.get("deposit_paid"):
        raise HTTPException(400, "Deposit already paid")
    settings = await get_settings()
    total = float(c.get("counter_amount") or c["budget"])
    pct = float(settings.get("deposit_percent", 50.0)) / 100.0
    amount = round(total * pct, 2)
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings["currency"],
                "product_data": {"name": f"Deposit ({int(pct*100)}%): {c['subject']}"},
                "unit_amount": int(round(amount * 100)),
            },
            "quantity": 1,
        }],
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        customer_email=user["email"],
        metadata={"kind": "commission_deposit", "commission_id": commission_id, "user_id": user["id"]},
    )
    await db.payment_transactions.insert_one({
        "id": new_id(), "session_id": session.id,
        "kind": "commission_deposit", "user_id": user["id"],
        "commission_id": commission_id, "artist_id": c["artist_id"],
        "amount": amount, "total": total, "currency": settings["currency"],
        "status": "initiated", "payment_status": "pending",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id, "amount": amount}


@router.post("/payments/commissions/{commission_id}/pay")
async def pay_commission(commission_id: str, req: CommissionPayReq, user: dict = Depends(get_current_user)):
    c = await db.commissions.find_one({"id": commission_id})
    if not c:
        raise HTTPException(404, "Commission not found")
    if c["buyer_id"] != user["id"]:
        raise HTTPException(403, "Not your commission")
    if c["status"] != "approved":
        raise HTTPException(400, "Commission not approved yet")
    if c.get("paid"):
        raise HTTPException(400, "Already paid")
    total = float(c.get("counter_amount") or c["budget"])
    deposit = float(c.get("deposit_amount") or 0)
    amount = round(total - deposit, 2)
    if amount <= 0:
        # No balance left → mark paid directly
        await db.commissions.update_one({"id": commission_id}, {"$set": {"paid": True, "status": "paid", "paid_at": now_iso()}})
        return {"checkout_url": None, "session_id": None, "free": True}
    settings = await get_settings()
    label = f"Balance: {c['subject']}" if deposit > 0 else f"Commission: {c['subject']}"
    from connect import build_transfer_options
    transfer_kwargs = await build_transfer_options(c["artist_id"], amount)
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings["currency"],
                "product_data": {"name": label},
                "unit_amount": int(round(amount * 100)),
            },
            "quantity": 1,
        }],
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        customer_email=user["email"],
        metadata={"kind": "commission_payment", "commission_id": commission_id, "user_id": user["id"]},
        **transfer_kwargs,
    )
    await db.payment_transactions.insert_one({
        "id": new_id(), "session_id": session.id,
        "kind": "commission_payment", "user_id": user["id"],
        "commission_id": commission_id, "artist_id": c["artist_id"],
        "amount": amount, "total": total, "currency": settings["currency"],
        "status": "initiated", "payment_status": "pending",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id, "amount": amount}


# ---------- Offer payment (buyer pays accepted offer) ----------
class OfferPayReq(BaseModel):
    origin_url: str


# ---------- Event ticket payment ----------
class EventTicketReq(BaseModel):
    origin_url: str


@router.post("/payments/events/{event_id}/ticket")
async def buy_event_ticket(event_id: str, req: EventTicketReq, user: dict = Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id})
    if not ev:
        raise HTTPException(404, "Event not found")
    if ev.get("cancelled"):
        raise HTTPException(400, "Event was cancelled")
    if ev.get("is_free"):
        raise HTTPException(400, "This is a free event — just RSVP")
    price = float(ev.get("ticket_price") or 0)
    if price <= 0:
        raise HTTPException(400, "Invalid ticket price")
    # No double buys
    existing = await db.event_rsvps.find_one({"event_id": event_id, "user_id": user["id"]})
    if existing:
        raise HTTPException(400, "You already have a ticket")
    if ev.get("max_capacity"):
        count = await db.event_rsvps.count_documents({"event_id": event_id})
        if count >= ev["max_capacity"]:
            raise HTTPException(400, "Event is sold out")
    settings = await get_settings()
    from connect import build_transfer_options
    transfer_kwargs = await build_transfer_options(ev["host_id"], price)
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings["currency"],
                "product_data": {"name": f"Ticket: {ev['title']}", "description": (ev.get("description") or "")[:400]},
                "unit_amount": int(round(price * 100)),
            },
            "quantity": 1,
        }],
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/events/{event_id}",
        customer_email=user["email"],
        metadata={"kind": "event_ticket", "event_id": event_id, "user_id": user["id"]},
        **transfer_kwargs,
    )
    await db.payment_transactions.insert_one({
        "id": new_id(), "session_id": session.id,
        "kind": "event_ticket", "user_id": user["id"],
        "event_id": event_id, "host_id": ev["host_id"],
        "amount": price, "currency": settings["currency"],
        "status": "initiated", "payment_status": "pending",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id, "amount": price}


class GiftTicketReq(BaseModel):
    origin_url: str
    recipient_email: str = Field(min_length=5, max_length=200)
    recipient_name: Optional[str] = Field(default=None, max_length=80)
    message: Optional[str] = Field(default=None, max_length=400)


@router.post("/payments/events/{event_id}/gift")
async def gift_event_ticket(event_id: str, req: GiftTicketReq, user: dict = Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id})
    if not ev:
        raise HTTPException(404, "Event not found")
    if ev.get("cancelled"):
        raise HTTPException(400, "Event was cancelled")
    if ev.get("is_free"):
        raise HTTPException(400, "Free events don't need a gifted ticket — just share the link")
    email = req.recipient_email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Enter a valid email for your friend")
    if ev.get("max_capacity"):
        count = await db.event_rsvps.count_documents({"event_id": event_id})
        if count >= ev["max_capacity"]:
            raise HTTPException(400, "Event is sold out")
    price = float(ev["ticket_price"])
    settings = await get_settings()
    from connect import build_transfer_options
    transfer_kwargs = await build_transfer_options(ev["host_id"], price)
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings["currency"],
                "product_data": {"name": f"Gift ticket: {ev['title']}", "description": f"For {req.recipient_name or email}"},
                "unit_amount": int(round(price * 100)),
            },
            "quantity": 1,
        }],
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/events/{event_id}",
        customer_email=user["email"],
        metadata={"kind": "event_ticket_gift", "event_id": event_id, "user_id": user["id"], "recipient_email": email},
        **transfer_kwargs,
    )
    await db.payment_transactions.insert_one({
        "id": new_id(), "session_id": session.id,
        "kind": "event_ticket_gift", "user_id": user["id"],
        "event_id": event_id, "host_id": ev["host_id"],
        "recipient_email": email, "recipient_name": (req.recipient_name or "").strip() or None,
        "gift_message": (req.message or "").strip() or None, "origin_url": req.origin_url.rstrip("/"),
        "amount": price, "currency": settings["currency"],
        "status": "initiated", "payment_status": "pending",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id, "amount": price}


@router.post("/payments/offers/{offer_id}/pay")
async def pay_offer(offer_id: str, req: OfferPayReq, user: dict = Depends(get_current_user)):
    o = await db.offers.find_one({"id": offer_id})
    if not o:
        raise HTTPException(404, "Offer not found")
    if o["buyer_id"] != user["id"]:
        raise HTTPException(403, "Not your offer")
    if o["status"] != "accepted":
        raise HTTPException(400, "Offer not accepted")
    if o.get("paid"):
        raise HTTPException(400, "Already paid")
    art = await db.artworks.find_one({"id": o["artwork_id"]})
    if not art:
        raise HTTPException(400, "Artwork missing")
    if art["status"] != "live":
        raise HTTPException(400, "Artwork no longer available")
    amount = float(o["amount"])
    settings = await get_settings()
    from connect import build_transfer_options
    transfer_kwargs = await build_transfer_options(o["artist_id"], amount)
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings["currency"],
                "product_data": {"name": f"Accepted offer: {art['title']}"},
                "unit_amount": int(round(amount * 100)),
            },
            "quantity": 1,
        }],
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        shipping_address_collection={"allowed_countries": ["US", "CA", "GB", "AU", "DE", "FR", "IT", "ES", "NL", "IE", "SE", "NO", "DK", "FI", "JP", "MX", "BR"]},
        customer_email=user["email"],
        metadata={"kind": "offer_payment", "offer_id": offer_id, "user_id": user["id"]},
        **transfer_kwargs,
    )
    await db.payment_transactions.insert_one({
        "id": new_id(), "session_id": session.id,
        "kind": "offer_payment", "user_id": user["id"],
        "offer_id": offer_id, "artwork_id": o["artwork_id"], "seller_id": o["artist_id"],
        "amount": amount, "currency": settings["currency"],
        "status": "initiated", "payment_status": "pending",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id, "amount": amount}


# ---------- Status ----------
async def _apply_gift_ticket(tx: dict, session_id: str):
    """Create the recipient's RSVP, email them the QR ticket, and receipt the gifter."""
    try:
        s = stripe.checkout.Session.retrieve(session_id)
        pi = getattr(s, "payment_intent", None)
        if pi:
            await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"payment_intent": pi}})
    except Exception:
        pass
    if await db.event_rsvps.find_one({"session_id": session_id}):
        return
    ev = await db.events.find_one({"id": tx["event_id"]}) or {}
    gifter = await db.users.find_one({"id": tx["user_id"]}) or {}
    recipient = await db.users.find_one({"email": tx["recipient_email"]})
    token = new_id()
    rsvp = {
        "id": new_id(), "event_id": tx["event_id"],
        "user_id": recipient["id"] if recipient else None,
        "user_name": tx.get("recipient_name") or (recipient or {}).get("name") or tx["recipient_email"].split("@")[0],
        "paid": True, "amount": float(tx["amount"]),
        "session_id": session_id, "created_at": now_iso(),
        "gift": True, "gifted_by": tx["user_id"], "gifted_by_name": gifter.get("name"),
        "gift_email": tx["recipient_email"], "gift_token": token, "gift_message": tx.get("gift_message"),
    }
    await db.event_rsvps.insert_one(rsvp)
    origin = tx.get("origin_url") or "https://artcorestudio.net"
    ticket_url = f"{origin}/gift/{token}"
    qr_url = f"{origin}/api/events/gift/{token}/qr.png"
    await db.notifications.insert_one({
        "id": new_id(), "user_id": tx["user_id"], "kind": "gift_ticket_sent",
        "event_id": tx["event_id"], "event_title": ev.get("title"), "recipient_email": tx["recipient_email"],
        "amount": float(tx["amount"]), "read": False, "created_at": now_iso(),
    })
    if recipient:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": recipient["id"], "kind": "gift_ticket_received",
            "event_id": tx["event_id"], "event_title": ev.get("title"), "from_user_name": gifter.get("name"),
            "read": False, "created_at": now_iso(),
        })
    try:
        from emails import send_email, gift_ticket_html, gift_sent_html, _fmt_when
        when = _fmt_when(ev.get("start_at", ""))
        loc = ev.get("location") or {}
        where = loc.get("city") or loc.get("address") or "TBA"
        import asyncio as _a
        _a.create_task(send_email(
            tx["recipient_email"], f"{gifter.get('name', 'A friend')} sent you a ticket: {ev.get('title')}",
            gift_ticket_html(rsvp["user_name"], gifter.get("name") or "A friend", ev.get("title") or "an event", when, where, tx.get("gift_message"), ticket_url, qr_url),
        ))
        if gifter.get("email"):
            _a.create_task(send_email(
                gifter["email"], f"Gift sent: {ev.get('title')}",
                gift_sent_html(gifter.get("name") or "there", tx["recipient_email"], ev.get("title") or "an event", float(tx["amount"]), when),
            ))
    except Exception:
        pass
    if tx.get("host_id") and tx["host_id"] != tx["user_id"]:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": tx["host_id"], "kind": "event_rsvp",
            "event_id": tx["event_id"], "event_title": ev.get("title"),
            "from_user_id": tx["user_id"], "from_user_name": f"{gifter.get('name', 'Someone')} (gift for {rsvp['user_name']})",
            "amount": float(tx["amount"]), "read": False, "created_at": now_iso(),
        })



async def _apply_paid(session_id: str):
    """Idempotent post-payment side effects."""
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx:
        return
    if tx.get("_paid_applied"):
        return
    if tx["kind"] == "buyer_order":
        settings = await get_settings()
        from waiver import settings_for_seller, consume_waiver_sale
        _seller_settings = {it["artist_id"]: await settings_for_seller(it["artist_id"], settings) for it in tx["items"]}
        _splits = [split_amount(it["price"] * it["quantity"], _seller_settings[it["artist_id"]]) for it in tx["items"]]
        from waiver import after_sale
        for _aid, _ss in _seller_settings.items():
            await after_sale(_aid, _ss)
        order = {
            "id": new_id(),
            "session_id": session_id,
            "buyer_id": tx.get("user_id"),
            "items": tx["items"],
            "total": tx["amount"],
            "currency": tx["currency"],
            "commission_percent": settings["commission_percent"],
            "platform_take": round(sum(s["platform_take"] for s in _splits), 2),
            "processing_fee": round(sum(s["processing_fee"] for s in _splits), 2),
            "artist_payouts": [
                {
                    "artist_id": it["artist_id"],
                    "artwork_id": it["artwork_id"],
                    "gross": round(it["price"] * it["quantity"], 2),
                    "processing_fee": sp["processing_fee"],
                    "net": sp["net"],
                    "status": "pending",
                }
                for it, sp in zip(tx["items"], _splits)
            ],
            "fulfillment": {"status": "pending", "shipped_at": None, "delivered_at": None, "tracking": None, "carrier": None},
            "created_at": now_iso(),
        }
        from payouts import hold_payouts
        order["artist_payouts"] = await hold_payouts(order["artist_payouts"])
        await db.orders.insert_one(order)
        # Mark artworks sold
        for it in tx["items"]:
            await db.artworks.update_one({"id": it["artwork_id"]}, {"$set": {"status": "sold"}})
        # Notifications
        if tx.get("user_id"):
            await db.notifications.insert_one({
                "id": new_id(), "user_id": tx["user_id"], "kind": "order_confirmed",
                "order_id": order["id"], "amount": tx["amount"],
                "read": False, "created_at": now_iso(),
            })
        seen_artists = set()
        for it in tx["items"]:
            if it["artist_id"] in seen_artists:
                continue
            seen_artists.add(it["artist_id"])
            await db.notifications.insert_one({
                "id": new_id(), "user_id": it["artist_id"], "kind": "artwork_sold",
                "order_id": order["id"], "artwork_id": it["artwork_id"],
                "amount": it["price"] * it["quantity"],
                "read": False, "created_at": now_iso(),
            })
    elif tx["kind"] == "upload_fee":
        await db.artworks.update_one({"id": tx["artwork_id"]}, {"$set": {"status": "live"}})
        _art = await db.artworks.find_one({"id": tx["artwork_id"]})
        if _art:
            from engage import notify_followers_soon
            _artist = await db.users.find_one({"id": _art["artist_id"]}) or {}
            notify_followers_soon(_art["artist_id"], "followed_new_artwork", f"New work from {_artist.get('name', 'an artist')}", _art["title"], f"/artwork/{_art['id']}", artwork_id=_art["id"])
    elif tx["kind"] == "auction_win":
        from waiver import settings_for_seller, consume_waiver_sale
        settings = await settings_for_seller(tx["seller_id"], await get_settings())
        gross = float(tx["amount"])
        sp = split_amount(gross, settings)
        from waiver import after_sale
        await after_sale(tx["seller_id"], settings)
        payout_status = "pending"  # → held by hold_payouts()
        order = {
            "id": new_id(),
            "session_id": session_id,
            "buyer_id": tx["user_id"],
            "items": [{"artwork_id": tx["artwork_id"], "artist_id": tx["seller_id"], "price": gross, "quantity": 1}],
            "total": gross,
            "currency": tx["currency"],
            "commission_percent": settings["commission_percent"],
            "platform_take": sp["platform_take"],
            "processing_fee": sp["processing_fee"],
            "artist_payouts": [{
                "artist_id": tx["seller_id"], "artwork_id": tx["artwork_id"],
                "gross": gross, "processing_fee": sp["processing_fee"], "net": sp["net"], "status": payout_status,
            }],
            "fulfillment": {"status": "pending", "shipped_at": None, "delivered_at": None, "tracking": None, "carrier": None},
            "source": "auction",
            "auction_id": tx["auction_id"],
            "created_at": now_iso(),
        }
        from payouts import hold_payouts
        order["artist_payouts"] = await hold_payouts(order["artist_payouts"])
        await db.orders.insert_one(order)
        await db.auctions.update_one({"id": tx["auction_id"]}, {"$set": {"paid": True, "order_id": order["id"], "paid_at": now_iso()}})
        # notify seller of settled payment
        await db.notifications.insert_one({
            "id": new_id(), "user_id": tx["seller_id"], "kind": "auction_paid",
            "auction_id": tx["auction_id"], "order_id": order["id"],
            "amount": gross, "read": False, "created_at": now_iso(),
        })
        await db.notifications.insert_one({
            "id": new_id(), "user_id": tx["user_id"], "kind": "order_confirmed",
            "order_id": order["id"], "amount": gross,
            "read": False, "created_at": now_iso(),
        })
    elif tx["kind"] == "commission_deposit":
        gross = float(tx["amount"])
        await db.commissions.update_one({"id": tx["commission_id"]}, {"$set": {
            "deposit_paid": True, "deposit_amount": gross, "deposit_paid_at": now_iso(),
        }})
        await db.notifications.insert_one({
            "id": new_id(), "user_id": tx["artist_id"], "kind": "commission_deposit",
            "commission_id": tx["commission_id"], "amount": gross,
            "read": False, "created_at": now_iso(),
        })
    elif tx["kind"] == "offer_payment":
        from waiver import settings_for_seller, consume_waiver_sale
        settings = await settings_for_seller(tx["seller_id"], await get_settings())
        gross = float(tx["amount"])
        sp = split_amount(gross, settings)
        from waiver import after_sale
        await after_sale(tx["seller_id"], settings)
        payout_status = "pending"  # → held by hold_payouts()
        order = {
            "id": new_id(),
            "session_id": session_id,
            "buyer_id": tx["user_id"],
            "items": [{"artwork_id": tx["artwork_id"], "artist_id": tx["seller_id"], "price": gross, "quantity": 1}],
            "total": gross,
            "currency": tx["currency"],
            "commission_percent": settings["commission_percent"],
            "platform_take": sp["platform_take"],
            "processing_fee": sp["processing_fee"],
            "artist_payouts": [{
                "artist_id": tx["seller_id"], "artwork_id": tx["artwork_id"],
                "gross": gross, "processing_fee": sp["processing_fee"], "net": sp["net"], "status": payout_status,
            }],
            "fulfillment": {"status": "pending", "shipped_at": None, "delivered_at": None, "tracking": None, "carrier": None},
            "source": "offer",
            "offer_id": tx["offer_id"],
            "created_at": now_iso(),
        }
        from payouts import hold_payouts
        order["artist_payouts"] = await hold_payouts(order["artist_payouts"])
        await db.orders.insert_one(order)
        await db.artworks.update_one({"id": tx["artwork_id"]}, {"$set": {"status": "sold"}})
        await db.offers.update_one({"id": tx["offer_id"]}, {"$set": {"paid": True, "status": "paid", "order_id": order["id"], "paid_at": now_iso()}})
        # auto-decline any other pending/countered offers on this artwork
        other_offers = await db.offers.find({
            "artwork_id": tx["artwork_id"], "id": {"$ne": tx["offer_id"]},
            "status": {"$in": ["pending", "countered"]},
        }).to_list(500)
        for other in other_offers:
            await db.offers.update_one({"id": other["id"]}, {"$set": {"status": "expired", "updated_at": now_iso()}})
            await db.notifications.insert_one({
                "id": new_id(), "user_id": other["buyer_id"], "kind": "offer_expired",
                "offer_id": other["id"], "artwork_id": tx["artwork_id"],
                "read": False, "created_at": now_iso(),
            })
        await db.notifications.insert_one({
            "id": new_id(), "user_id": tx["seller_id"], "kind": "offer_paid",
            "offer_id": tx["offer_id"], "order_id": order["id"], "artwork_id": tx["artwork_id"],
            "amount": gross, "read": False, "created_at": now_iso(),
        })
        await db.notifications.insert_one({
            "id": new_id(), "user_id": tx["user_id"], "kind": "order_confirmed",
            "order_id": order["id"], "amount": gross,
            "read": False, "created_at": now_iso(),
        })
    elif tx["kind"] == "commission_payment":
        from waiver import settings_for_seller, consume_waiver_sale
        settings = await settings_for_seller(tx["artist_id"], await get_settings())
        gross = float(tx["amount"])
        sp = split_amount(gross, settings)
        from waiver import after_sale
        await after_sale(tx["artist_id"], settings)
        await db.commissions.update_one({"id": tx["commission_id"]}, {"$set": {
            "paid": True, "paid_at": now_iso(), "status": "paid",
            "platform_take": sp["platform_take"],
            "processing_fee": sp["processing_fee"],
            "net_to_artist": sp["net"],
        }})
        await db.notifications.insert_one({
            "id": new_id(), "user_id": tx["artist_id"], "kind": "commission_paid",
            "commission_id": tx["commission_id"], "amount": gross,
            "read": False, "created_at": now_iso(),
        })
    elif tx["kind"] == "event_ticket_gift":
        await _apply_gift_ticket(tx, session_id)
    elif tx["kind"] == "pro_subscription":
        from pro import apply_pro_checkout
        await apply_pro_checkout(tx, session_id)
    elif tx["kind"] == "event_ticket":
        # Persist payment_intent for future refunds
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            pi = getattr(s, "payment_intent", None)
            if pi:
                await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"payment_intent": pi}})
        except Exception:
            pass
        # Mark waitlist hold as claimed (if this session came from a hold)
        if tx.get("waitlist_hold"):
            await db.waitlist_holds.update_one(
                {"session_id": session_id},
                {"$set": {"claimed": True, "claimed_at": now_iso()}},
            )
        # Idempotency: only create RSVP once per session
        existing_rsvp = await db.event_rsvps.find_one({"event_id": tx["event_id"], "user_id": tx["user_id"]})
        if not existing_rsvp:
            user_doc = await db.users.find_one({"id": tx["user_id"]}) or {}
            await db.event_rsvps.insert_one({
                "id": new_id(), "event_id": tx["event_id"], "user_id": tx["user_id"],
                "user_name": user_doc.get("name", "Guest"),
                "paid": True, "amount": float(tx["amount"]),
                "session_id": tx["session_id"], "created_at": now_iso(),
            })
        ev = await db.events.find_one({"id": tx["event_id"]}) or {}
        # Notify buyer
        await db.notifications.insert_one({
            "id": new_id(), "user_id": tx["user_id"], "kind": "event_ticket_paid",
            "event_id": tx["event_id"], "event_title": ev.get("title"),
            "amount": float(tx["amount"]),
            "read": False, "created_at": now_iso(),
        })
        # Ticket confirmation email
        try:
            from emails import send_email, ticket_receipt_html
            from datetime import datetime as _dt
            buyer = await db.users.find_one({"id": tx["user_id"]}) or {}
            if buyer.get("email"):
                when = ev.get("start_at", "")
                try:
                    when = _dt.fromisoformat(when.replace("Z", "+00:00")).strftime("%b %d, %Y · %-I:%M %p")
                except Exception:
                    pass
                where = (ev.get("location") or {}).get("city") or (ev.get("location") or {}).get("address") or "TBA"
                html = ticket_receipt_html(
                    user_name=buyer.get("name") or "there",
                    event_title=ev.get("title") or "your event",
                    amount=float(tx["amount"]),
                    event_when=when,
                    event_where=where,
                )
                import asyncio as _a3
                _a3.create_task(send_email(buyer["email"], f"You're going: {ev.get('title')}", html))
        except Exception:
            pass
        # Notify host
        if tx.get("host_id") and tx["host_id"] != tx["user_id"]:
            await db.notifications.insert_one({
                "id": new_id(), "user_id": tx["host_id"], "kind": "event_rsvp",
                "event_id": tx["event_id"], "event_title": ev.get("title"),
                "from_user_id": tx["user_id"], "from_user_name": (user_doc.get("name") if not existing_rsvp else ""),
                "amount": float(tx["amount"]), "read": False, "created_at": now_iso(),
            })
            try:
                from push import send_push
                import asyncio as _a
                _a.create_task(send_push(
                    tx["host_id"],
                    title="New paid ticket",
                    body=f"${int(tx['amount']):,} · {ev.get('title', 'your event')}",
                    url=f"/events/{tx['event_id']}",
                    kind="event_rsvp",
                ))
            except Exception:
                pass
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"_paid_applied": True}})


@router.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx:
        raise HTTPException(404, "Not found")
    if tx.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid", "updated_at": now_iso()}},
                )
                await _apply_paid(session_id)
                tx = await db.payment_transactions.find_one({"session_id": session_id})
        except stripe.error.StripeError:
            pass
    return {
        "session_id": tx["session_id"],
        "status": tx["status"],
        "payment_status": tx["payment_status"],
        "kind": tx["kind"],
    }


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        from stripe_config import webhook_secret
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret())
    except Exception:
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"), "updated_at": now_iso()}},
        )
        await _apply_paid(obj["id"])
    elif t in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        from pro import sync_subscription
        await sync_subscription(obj)
    elif t == "invoice.payment_failed":
        user = await db.users.find_one({"stripe_customer_id": obj.get("customer")})
        if user:
            await db.notifications.insert_one({"id": new_id(), "user_id": user["id"], "kind": "pro_payment_failed", "read": False, "created_at": now_iso()})
    return {"ok": True}
