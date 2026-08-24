"""Order history + reviews for buyers/artists."""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user

router = APIRouter(prefix="/api", tags=["orders-reviews"])


async def _enrich_order(o: dict) -> dict:
    o = strip_mongo(o)
    if not o:
        return o
    # attach artwork thumbnails + artist names
    items_enriched = []
    for it in o.get("items", []):
        art = await db.artworks.find_one({"id": it["artwork_id"]})
        artist = await db.users.find_one({"id": it["artist_id"]})
        items_enriched.append({
            **it,
            "artwork": {"id": art["id"], "title": art["title"], "images": art.get("images", [])[:1]} if art else None,
            "artist_name": artist["name"] if artist else None,
        })
    o["items"] = items_enriched
    return o


@router.get("/orders/mine")
async def my_orders(user: dict = Depends(get_current_user)):
    cursor = db.orders.find({"buyer_id": user["id"]}).sort("created_at", -1).limit(200)
    return [await _enrich_order(o) for o in await cursor.to_list(200)]


@router.get("/orders/selling")
async def selling_orders(user: dict = Depends(get_current_user)):
    """All orders where the current user is a seller on any line."""
    cursor = db.orders.find({"artist_payouts.artist_id": user["id"]}).sort("created_at", -1).limit(200)
    return [await _enrich_order(o) for o in await cursor.to_list(200)]


class ShipReq(BaseModel):
    carrier: str = Field(min_length=1, max_length=80)
    tracking: str = Field(min_length=1, max_length=200)
    note: Optional[str] = None


@router.post("/orders/{oid}/ship")
async def ship_order(oid: str, req: ShipReq, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    is_seller = any(p["artist_id"] == user["id"] for p in o.get("artist_payouts", []))
    if not is_seller and user["role"] != "admin":
        raise HTTPException(403, "Not the seller")
    current = (o.get("fulfillment") or {}).get("status", "pending")
    if current not in ("pending",):
        raise HTTPException(400, f"Cannot ship — order status is {current}")
    await db.orders.update_one({"id": oid}, {"$set": {
        "fulfillment.status": "shipped",
        "fulfillment.shipped_at": now_iso(),
        "fulfillment.carrier": req.carrier,
        "fulfillment.tracking": req.tracking,
        "fulfillment.note": req.note,
    }})
    if o.get("buyer_id"):
        await db.notifications.insert_one({
            "id": new_id(), "user_id": o["buyer_id"], "kind": "order_shipped",
            "order_id": oid, "carrier": req.carrier, "tracking": req.tracking,
            "read": False, "created_at": now_iso(),
        })
    return await _enrich_order(await db.orders.find_one({"id": oid}))


@router.post("/orders/{oid}/mark-delivered")
async def mark_delivered(oid: str, user: dict = Depends(get_current_user)):
    """Buyer confirms delivery (releases payout markers)."""
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    if o.get("buyer_id") != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not the buyer")
    current = (o.get("fulfillment") or {}).get("status", "pending")
    if current not in ("shipped",):
        raise HTTPException(400, f"Cannot mark delivered — status is {current}")
    # Release payouts. If payout wasn't auto-transferred at checkout AND seller has Connect,
    # kick off a real Stripe Transfer now. Otherwise mark released (platform holds funds).
    from connect import transfer_manual
    payouts = o.get("artist_payouts", [])
    for p in payouts:
        if p.get("status") == "auto_transferred":
            # Already sent to artist at charge time via destination charge
            p["status"] = "auto_transferred"
            continue
        # Attempt live transfer if Connect is enabled
        try:
            result = await transfer_manual(p["artist_id"], p["net"], source_reference=f"order:{oid}", description=f"Art Core payout for order {oid[:8]}")
            if result:
                p["status"] = "transferred"
                p["stripe_transfer_id"] = result["transfer_id"]
            else:
                p["status"] = "released"  # platform holds funds; artist paid manually
        except Exception as e:
            # Fallback: mark released but log the reason
            p["status"] = "released"
            p["transfer_error"] = str(e)[:200]
    await db.orders.update_one({"id": oid}, {"$set": {
        "fulfillment.status": "delivered",
        "fulfillment.delivered_at": now_iso(),
        "artist_payouts": payouts,
    }})
    for p in payouts:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": p["artist_id"], "kind": "payout_released",
            "order_id": oid, "artwork_id": p["artwork_id"], "amount": p["net"],
            "read": False, "created_at": now_iso(),
        })
    return await _enrich_order(await db.orders.find_one({"id": oid}))


@router.get("/orders/{oid}")
async def get_order(oid: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    is_buyer = o.get("buyer_id") == user["id"]
    is_seller = any(p["artist_id"] == user["id"] for p in o.get("artist_payouts", []))
    if not (is_buyer or is_seller or user["role"] == "admin"):
        raise HTTPException(403, "Not yours")
    return await _enrich_order(o)


# ---------- Reviews ----------
class ReviewCreate(BaseModel):
    order_id: str
    artwork_id: str
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=1, max_length=2000)


@router.post("/reviews")
async def create_review(req: ReviewCreate, user: dict = Depends(get_current_user)):
    order = await db.orders.find_one({"id": req.order_id})
    if not order or order.get("buyer_id") != user["id"]:
        raise HTTPException(404, "Order not found")
    if not any(it["artwork_id"] == req.artwork_id for it in order.get("items", [])):
        raise HTTPException(400, "Artwork not in this order")
    if await db.reviews.find_one({"order_id": req.order_id, "artwork_id": req.artwork_id, "buyer_id": user["id"]}):
        raise HTTPException(400, "Already reviewed")
    art = await db.artworks.find_one({"id": req.artwork_id})
    rev = {
        "id": new_id(),
        "order_id": req.order_id, "artwork_id": req.artwork_id,
        "artist_id": art["artist_id"] if art else None,
        "buyer_id": user["id"], "buyer_name": user["name"],
        "rating": req.rating, "text": req.text,
        "created_at": now_iso(),
    }
    await db.reviews.insert_one(rev)
    # notify artist
    if art:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": art["artist_id"], "kind": "new_review",
            "review_id": rev["id"], "artwork_id": req.artwork_id,
            "rating": req.rating, "read": False, "created_at": now_iso(),
        })
    return strip_mongo(rev)


@router.get("/artworks/{aid}/reviews")
async def artwork_reviews(aid: str):
    cursor = db.reviews.find({"artwork_id": aid}).sort("created_at", -1).limit(100)
    return [strip_mongo(r) for r in await cursor.to_list(100)]


@router.get("/artists/{aid}/reviews")
async def artist_reviews(aid: str):
    cursor = db.reviews.find({"artist_id": aid}).sort("created_at", -1).limit(100)
    revs = [strip_mongo(r) for r in await cursor.to_list(100)]
    avg = round(sum(r["rating"] for r in revs) / len(revs), 2) if revs else None
    return {"count": len(revs), "avg_rating": avg, "reviews": revs}


@router.get("/reviews/eligible")
async def eligible_reviews(user: dict = Depends(get_current_user)):
    """Return artwork_ids the current buyer can review (bought + not yet reviewed)."""
    orders = await db.orders.find({"buyer_id": user["id"]}).to_list(500)
    out = []
    for o in orders:
        for it in o.get("items", []):
            existing = await db.reviews.find_one({"order_id": o["id"], "artwork_id": it["artwork_id"], "buyer_id": user["id"]})
            if existing:
                continue
            art = await db.artworks.find_one({"id": it["artwork_id"]})
            if art:
                out.append({"order_id": o["id"], "artwork_id": it["artwork_id"],
                            "title": art["title"], "images": art.get("images", [])[:1]})
    return out
