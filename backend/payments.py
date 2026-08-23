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
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

router = APIRouter(prefix="/api", tags=["payments"])


async def get_settings() -> dict:
    s = await db.settings.find_one({"id": "global"})
    if not s:
        default = {
            "id": "global",
            "commission_percent": 15.0,
            "upload_fee": 5.0,
            "currency": "usd",
            "aotw_artwork_id": None,
            "created_at": now_iso(),
        }
        await db.settings.insert_one(default)
        return default
    return strip_mongo(s)


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
    amount = float(au.get("final_price") or au.get("current_bid") or 0)
    if amount <= 0:
        raise HTTPException(400, "Invalid amount")
    art = await db.artworks.find_one({"id": au["artwork_id"]})
    settings = await get_settings()
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


# ---------- Commission payment ----------
class CommissionPayReq(BaseModel):
    origin_url: str


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
    amount = float(c.get("counter_amount") or c["budget"])
    settings = await get_settings()
    artist = await db.users.find_one({"id": c["artist_id"]})
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings["currency"],
                "product_data": {"name": f"Commission: {c['subject']}"},
                "unit_amount": int(round(amount * 100)),
            },
            "quantity": 1,
        }],
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        customer_email=user["email"],
        metadata={"kind": "commission_payment", "commission_id": commission_id, "user_id": user["id"]},
    )
    await db.payment_transactions.insert_one({
        "id": new_id(), "session_id": session.id,
        "kind": "commission_payment", "user_id": user["id"],
        "commission_id": commission_id, "artist_id": c["artist_id"],
        "amount": amount, "currency": settings["currency"],
        "status": "initiated", "payment_status": "pending",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


# ---------- Status ----------
async def _apply_paid(session_id: str):
    """Idempotent post-payment side effects."""
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx:
        return
    if tx.get("_paid_applied"):
        return
    if tx["kind"] == "buyer_order":
        settings = await get_settings()
        commission = float(settings["commission_percent"]) / 100.0
        order = {
            "id": new_id(),
            "session_id": session_id,
            "buyer_id": tx.get("user_id"),
            "items": tx["items"],
            "total": tx["amount"],
            "currency": tx["currency"],
            "commission_percent": settings["commission_percent"],
            "platform_take": round(tx["amount"] * commission, 2),
            "artist_payouts": [
                {
                    "artist_id": it["artist_id"],
                    "artwork_id": it["artwork_id"],
                    "gross": round(it["price"] * it["quantity"], 2),
                    "net": round(it["price"] * it["quantity"] * (1 - commission), 2),
                    "status": "pending",
                }
                for it in tx["items"]
            ],
            "created_at": now_iso(),
        }
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
    elif tx["kind"] == "auction_win":
        settings = await get_settings()
        commission = float(settings["commission_percent"]) / 100.0
        gross = float(tx["amount"])
        order = {
            "id": new_id(),
            "session_id": session_id,
            "buyer_id": tx["user_id"],
            "items": [{"artwork_id": tx["artwork_id"], "artist_id": tx["seller_id"], "price": gross, "quantity": 1}],
            "total": gross,
            "currency": tx["currency"],
            "commission_percent": settings["commission_percent"],
            "platform_take": round(gross * commission, 2),
            "artist_payouts": [{
                "artist_id": tx["seller_id"], "artwork_id": tx["artwork_id"],
                "gross": gross, "net": round(gross * (1 - commission), 2), "status": "pending",
            }],
            "source": "auction",
            "auction_id": tx["auction_id"],
            "created_at": now_iso(),
        }
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
    elif tx["kind"] == "commission_payment":
        settings = await get_settings()
        commission = float(settings["commission_percent"]) / 100.0
        gross = float(tx["amount"])
        await db.commissions.update_one({"id": tx["commission_id"]}, {"$set": {
            "paid": True, "paid_at": now_iso(), "status": "paid",
            "platform_take": round(gross * commission, 2),
            "net_to_artist": round(gross * (1 - commission), 2),
        }})
        await db.notifications.insert_one({
            "id": new_id(), "user_id": tx["artist_id"], "kind": "commission_paid",
            "commission_id": tx["commission_id"], "amount": gross,
            "read": False, "created_at": now_iso(),
        })
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
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"), "updated_at": now_iso()}},
        )
        await _apply_paid(obj["id"])
    return {"ok": True}
