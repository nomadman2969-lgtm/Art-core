"""Artist dashboard endpoints — sales, payouts, connect."""
from fastapi import APIRouter, Depends
from db import db, strip_mongo
from auth import require_role
import os

router = APIRouter(prefix="/api/artist", tags=["artist"])

STRIPE_ONBOARDING_URL = os.environ.get("STRIPE_ONBOARDING_URL", "")


@router.get("/dashboard")
async def dashboard(user: dict = Depends(require_role("artist", "admin"))):
    live = await db.artworks.count_documents({"artist_id": user["id"], "status": "live"})
    sold = await db.artworks.count_documents({"artist_id": user["id"], "status": "sold"})
    pending = await db.artworks.count_documents({"artist_id": user["id"], "status": "pending_fee"})
    orders_cursor = db.orders.find({"artist_payouts.artist_id": user["id"]}).sort("created_at", -1)
    orders = await orders_cursor.to_list(500)
    my_payouts = []
    total_gross = 0.0
    total_net = 0.0
    for o in orders:
        for p in o.get("artist_payouts", []):
            if p["artist_id"] == user["id"]:
                total_gross += p["gross"]
                total_net += p["net"]
                my_payouts.append({
                    "order_id": o["id"],
                    "artwork_id": p["artwork_id"],
                    "gross": p["gross"],
                    "net": p["net"],
                    "status": p["status"],
                    "created_at": o["created_at"],
                })
    return {
        "listings": {"live": live, "sold": sold, "pending_fee": pending},
        "total_gross": round(total_gross, 2),
        "total_net": round(total_net, 2),
        "payouts": my_payouts,
        "stripe_connect_status": user.get("stripe_connect_status", "not_started"),
        "stripe_onboarding_url": STRIPE_ONBOARDING_URL,
    }


@router.post("/connect/start")
async def start_connect(user: dict = Depends(require_role("artist", "admin"))):
    await db.users.update_one({"id": user["id"]}, {"$set": {"stripe_connect_status": "pending"}})
    return {"onboarding_url": STRIPE_ONBOARDING_URL, "status": "pending"}


@router.post("/connect/complete")
async def complete_connect(user: dict = Depends(require_role("artist", "admin"))):
    """Mock endpoint — artist clicks 'I completed onboarding' after Stripe flow."""
    await db.users.update_one({"id": user["id"]}, {"$set": {"stripe_connect_status": "connected"}})
    return {"status": "connected"}
