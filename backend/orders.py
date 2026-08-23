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
