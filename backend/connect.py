"""Stripe Connect Express: artist onboarding, account status, and destination-charge helpers.

Design:
- Artists onboard via /api/connect/onboarding-link → returns Stripe-hosted account link URL.
- Webhook (account.updated) tracks charges_enabled / payouts_enabled.
- payments.py imports `build_transfer_options(seller_id, gross_amount)` to attach
  transfer_data + application_fee_amount to Checkout Sessions where a single seller
  is identified. If the seller has no connected account (or it's not fully enabled),
  no transfer is attached — funds land on the platform account and the payout stays
  pending in `artist_payouts` for manual settlement (current behavior).
"""
import os
import stripe
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, require_role

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

router = APIRouter(prefix="/api/connect", tags=["connect"])


async def _get_settings():
    from payments import get_settings
    return await get_settings()


# ---------- Onboarding ----------
class OnboardReq(BaseModel):
    return_url: str
    refresh_url: Optional[str] = None


@router.post("/onboarding-link")
async def onboarding_link(req: OnboardReq, user: dict = Depends(require_role("artist", "admin"))):
    """Create (or reuse) a Stripe Connect Express account and return a hosted onboarding link."""
    account_id = user.get("stripe_account_id")
    try:
        if not account_id:
            acct = stripe.Account.create(
                type="express",
                email=user["email"],
                capabilities={
                    "transfers": {"requested": True},
                    "card_payments": {"requested": True},
                },
                business_type="individual",
                business_profile={"product_description": f"Original artwork by {user['name']} on Art Core"},
                metadata={"art_core_user_id": user["id"]},
            )
            account_id = acct.id
            await db.users.update_one({"id": user["id"]}, {"$set": {
                "stripe_account_id": account_id,
                "stripe_account_status": "pending",
                "stripe_charges_enabled": False,
                "stripe_payouts_enabled": False,
            }})
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=req.refresh_url or req.return_url,
            return_url=req.return_url,
            type="account_onboarding",
        )
        return {"url": link.url, "account_id": account_id}
    except stripe.error.StripeError as e:
        # Connect may not be enabled on this Stripe account/sandbox
        raise HTTPException(400, f"Stripe Connect not available: {e.user_message or str(e)[:200]}")


@router.get("/status")
async def get_status(user: dict = Depends(get_current_user)):
    """Returns current artist's Connect account status."""
    account_id = user.get("stripe_account_id")
    if not account_id:
        return {"connected": False, "charges_enabled": False, "payouts_enabled": False, "requirements_due": None}
    try:
        acct = stripe.Account.retrieve(account_id)
        # Cache latest
        await db.users.update_one({"id": user["id"]}, {"$set": {
            "stripe_charges_enabled": bool(acct.charges_enabled),
            "stripe_payouts_enabled": bool(acct.payouts_enabled),
            "stripe_account_status": "active" if acct.charges_enabled and acct.payouts_enabled else "pending",
        }})
        return {
            "connected": True,
            "account_id": account_id,
            "charges_enabled": bool(acct.charges_enabled),
            "payouts_enabled": bool(acct.payouts_enabled),
            "details_submitted": bool(acct.details_submitted),
            "requirements_due": (acct.requirements.currently_due or []) if getattr(acct, "requirements", None) else [],
        }
    except stripe.error.StripeError as e:
        return {"connected": True, "account_id": account_id, "charges_enabled": False, "payouts_enabled": False, "error": str(e)[:200]}


@router.post("/dashboard-link")
async def dashboard_link(user: dict = Depends(get_current_user)):
    """Login link to Stripe Express dashboard where artists see their balances/payouts."""
    account_id = user.get("stripe_account_id")
    if not account_id:
        raise HTTPException(400, "No connected account yet")
    try:
        link = stripe.Account.create_login_link(account_id)
        return {"url": link.url}
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Cannot create dashboard link: {str(e)[:200]}")


# ---------- Helper for payments.py ----------
async def build_transfer_options(seller_id: str, gross_amount: float) -> dict:
    """If the seller has an active Connect account, return kwargs for stripe.checkout.Session.create
    that route the seller's cut to them and take an application_fee. If not, return {}."""
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        return {}
    account_id = seller.get("stripe_account_id")
    if not account_id or not seller.get("stripe_charges_enabled"):
        return {}
    settings = await _get_settings()
    fee_pct = float(settings["commission_percent"]) / 100.0
    application_fee_cents = int(round(gross_amount * fee_pct * 100))
    return {
        "payment_intent_data": {
            "application_fee_amount": application_fee_cents,
            "transfer_data": {"destination": account_id},
        },
    }


async def transfer_manual(seller_id: str, amount: float, source_reference: str, description: str = "") -> Optional[dict]:
    """Manual transfer helper — used when we couldn't route at checkout time (e.g. bundled
    multi-seller order). Returns the transfer dict or None if seller has no active account."""
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        return None
    account_id = seller.get("stripe_account_id")
    if not account_id or not seller.get("stripe_payouts_enabled"):
        return None
    settings = await _get_settings()
    tr = stripe.Transfer.create(
        amount=int(round(amount * 100)),
        currency=settings["currency"],
        destination=account_id,
        description=description or f"Art Core payout · {source_reference}",
        metadata={"source": source_reference, "art_core_user_id": seller_id},
    )
    await db.transfers.insert_one({
        "id": new_id(),
        "stripe_transfer_id": tr.id,
        "seller_id": seller_id,
        "amount": amount,
        "currency": settings["currency"],
        "source": source_reference,
        "created_at": now_iso(),
    })
    return {"transfer_id": tr.id, "amount": amount}
