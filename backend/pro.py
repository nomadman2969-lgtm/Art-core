"""Art Core Pro: $12/mo or $99/yr subscription via Stripe Billing. Founders get 50% off for life.
Perks: boosted placement, premium studio themes, daily payouts, Pro badge."""
import os
from datetime import datetime, timezone
from typing import Optional
import stripe
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso
from auth import get_current_user, get_optional_user

router = APIRouter(prefix="/api/pro", tags=["pro"])

PRODUCT_ID = "art_core_pro"
PRICES = {"month": {"lookup_key": "pro_monthly", "amount": 1200}, "year": {"lookup_key": "pro_yearly", "amount": 9900}}
FOUNDER_COUPON = "founding50"
PERKS = [
    ("Boosted placement", "Your pieces rank first in Explore and the Marketplace, with a Pro tag."),
    ("Premium studio themes", "Unlock the Pro theme set and custom accent colors for your studio."),
    ("Faster payouts", "Same-day release when the collector confirms delivery (standard: 2 days), and a 5-day safety hold instead of 10."),
    ("Pro badge", "A Pro mark on your profile and every artwork card."),
]


def ensure_pro_catalog() -> None:
    """Idempotent: product, monthly/yearly prices by lookup_key, founder coupon."""
    product = None
    for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        if (p.to_dict().get("metadata") or {}).get("emergent_product_id") == PRODUCT_ID:
            product = p
            break
    if not product:
        product = stripe.Product.create(name="Art Core Pro", tax_code="txcd_10103001",
                                        metadata={"managed_by": "emergent", "emergent_product_id": PRODUCT_ID})
    for interval, cfg in PRICES.items():
        existing = stripe.Price.list(lookup_keys=[cfg["lookup_key"]], active=True, limit=1).data
        if existing and existing[0].unit_amount != cfg["amount"]:
            stripe.Price.modify(existing[0].id, active=False)
            existing = []
        if not existing:
            stripe.Price.create(product=product.id, unit_amount=cfg["amount"], currency="usd", lookup_key=cfg["lookup_key"],
                                transfer_lookup_key=True, recurring={"interval": interval})
    try:
        stripe.Coupon.retrieve(FOUNDER_COUPON)
    except stripe.error.InvalidRequestError:
        stripe.Coupon.create(id=FOUNDER_COUPON, percent_off=50, duration="forever", name="Founding artist · 50% off for life")


def pro_active(user: dict) -> bool:
    pro = user.get("pro") or {}
    if pro.get("status") not in ("active", "trialing", "past_due"):
        return False
    end = pro.get("current_period_end")
    return not end or end > datetime.now(timezone.utc).timestamp() - 3 * 86400  # 3-day grace


async def _customer_id(user: dict) -> str:
    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]
    c = stripe.Customer.create(email=user["email"], name=user.get("name"), metadata={"user_id": user["id"]})
    await db.users.update_one({"id": user["id"]}, {"$set": {"stripe_customer_id": c.id}})
    return c.id


async def apply_payout_schedule(user: dict, pro: bool) -> None:
    acct = user.get("stripe_account_id")
    if not acct:
        return
    try:
        stripe.Account.modify(acct, settings={"payouts": {"schedule": {"interval": "daily" if pro else "weekly", **({} if pro else {"weekly_anchor": "friday"})}}})
    except stripe.error.StripeError:
        pass


async def sync_subscription(sub) -> Optional[dict]:
    """Mirror a Stripe subscription onto the owning user."""
    sub = sub if isinstance(sub, dict) else sub.to_dict()
    user = await db.users.find_one({"stripe_customer_id": sub["customer"]})
    if not user:
        return None
    item = (sub.get("items") or {}).get("data", [{}])[0]
    price = item.get("price") or {}
    pro = {
        "status": sub["status"], "subscription_id": sub["id"],
        "interval": (price.get("recurring") or {}).get("interval"), "amount": (price.get("unit_amount") or 0) / 100,
        "current_period_end": sub.get("current_period_end") or item.get("current_period_end"),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "discount": bool(sub.get("discount") or sub.get("discounts")),
        "updated_at": now_iso(),
    }
    await db.users.update_one({"id": user["id"]}, {"$set": {"pro": pro}})
    fresh = {**user, "pro": pro}
    await apply_payout_schedule(fresh, pro_active(fresh))
    return pro


class CheckoutReq(BaseModel):
    interval: str = Field(pattern="^(month|year)$")
    origin_url: str


@router.get("/plans")
async def plans(user: Optional[dict] = Depends(get_optional_user)):
    founder = bool(user and user.get("founding_member"))
    return {
        "perks": [{"title": t, "body": b} for t, b in PERKS],
        "founder_discount": founder,
        "prices": {k: {"amount": v["amount"] / 100, "founder_amount": v["amount"] / 200 if founder else None} for k, v in PRICES.items()},
    }


@router.get("/status")
async def status(user: dict = Depends(get_current_user)):
    return {"active": pro_active(user), **(user.get("pro") or {}), "founding_member": bool(user.get("founding_member"))}


@router.post("/checkout")
async def checkout(req: CheckoutReq, user: dict = Depends(get_current_user)):
    if user.get("role") != "artist":
        raise HTTPException(400, "Pro is for artist accounts")
    if pro_active(user):
        raise HTTPException(400, "You're already on Pro")
    prices = stripe.Price.list(lookup_keys=[PRICES[req.interval]["lookup_key"]], active=True, limit=1).data
    if not prices:
        ensure_pro_catalog()
        prices = stripe.Price.list(lookup_keys=[PRICES[req.interval]["lookup_key"]], active=True, limit=1).data
    kwargs = dict(
        mode="subscription", customer=await _customer_id(user),
        line_items=[{"price": prices[0].id, "quantity": 1}],
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/pro",
        metadata={"kind": "pro_subscription", "user_id": user["id"], "interval": req.interval},
        subscription_data={"metadata": {"user_id": user["id"]}},
    )
    if user.get("founding_member"):
        kwargs["discounts"] = [{"coupon": FOUNDER_COUPON}]
    else:
        kwargs["allow_promotion_codes"] = True
    session = stripe.checkout.Session.create(**kwargs)
    await db.payment_transactions.insert_one({
        "id": new_id(), "session_id": session.id, "kind": "pro_subscription", "user_id": user["id"],
        "interval": req.interval, "amount": PRICES[req.interval]["amount"] / 100 / (2 if user.get("founding_member") else 1), "currency": "usd",
        "status": "initiated", "payment_status": "pending", "created_at": now_iso(), "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


async def apply_pro_checkout(tx: dict, session_id: str) -> None:
    s = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
    if s.get("subscription"):
        await sync_subscription(s["subscription"])
    await db.notifications.insert_one({"id": new_id(), "user_id": tx["user_id"], "kind": "pro_activated", "read": False, "created_at": now_iso()})


@router.post("/cancel")
async def cancel(user: dict = Depends(get_current_user)):
    sub_id = (user.get("pro") or {}).get("subscription_id")
    if not sub_id:
        raise HTTPException(400, "No active subscription")
    sub = stripe.Subscription.modify(sub_id, cancel_at_period_end=True)
    return await sync_subscription(sub)


@router.post("/resume")
async def resume(user: dict = Depends(get_current_user)):
    sub_id = (user.get("pro") or {}).get("subscription_id")
    if not sub_id:
        raise HTTPException(400, "No subscription")
    sub = stripe.Subscription.modify(sub_id, cancel_at_period_end=False)
    return await sync_subscription(sub)


class PortalReq(BaseModel):
    origin_url: str


@router.post("/portal")
async def portal(req: PortalReq, user: dict = Depends(get_current_user)):
    if not user.get("stripe_customer_id"):
        raise HTTPException(400, "No billing account yet")
    try:
        ps = stripe.billing_portal.Session.create(customer=user["stripe_customer_id"], return_url=f"{req.origin_url}/pro")
        return {"url": ps.url}
    except stripe.error.StripeError as e:
        raise HTTPException(400, (e.user_message or "Billing portal isn't configured yet — use cancel/resume here")[:160])
