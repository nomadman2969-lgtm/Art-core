"""Notifications inbox — reads generated notification docs from auctions/commissions/follows."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


async def _enrich(n: dict) -> dict:
    n = strip_mongo(n)
    if not n:
        return n
    kind = n.get("kind")
    if kind in ("outbid", "auction_won", "auction_sold", "auction_forfeited", "auction_cancelled", "auction_deadline_soon", "watched_auction_leader", "auction_paid") and n.get("auction_id"):
        au = await db.auctions.find_one({"id": n["auction_id"]})
        if au and au.get("artwork_id"):
            art = await db.artworks.find_one({"id": au["artwork_id"]})
            if art:
                n["artwork"] = {"id": art["id"], "title": art["title"], "images": art.get("images", [])[:1]}
        n["auction"] = {"id": n["auction_id"]}
    if kind and kind.startswith("commission_") and n.get("commission_id"):
        c = await db.commissions.find_one({"id": n["commission_id"]})
        if c:
            n["commission"] = {"id": c["id"], "subject": c["subject"], "status": c["status"]}
            other_id = c["buyer_id"] if n["user_id"] == c["artist_id"] else c["artist_id"]
            other = await db.users.find_one({"id": other_id})
            if other:
                n["other"] = {"id": other["id"], "name": other["name"]}
    if kind and kind.startswith("offer_") and n.get("offer_id"):
        offer = await db.offers.find_one({"id": n["offer_id"]})
        if offer:
            n["offer"] = {"id": offer["id"], "status": offer["status"], "amount": offer.get("amount"), "counter_amount": offer.get("counter_amount")}
        if n.get("artwork_id"):
            art = await db.artworks.find_one({"id": n["artwork_id"]})
            if art:
                n["artwork"] = {"id": art["id"], "title": art["title"], "images": art.get("images", [])[:1]}
    if kind == "order_shipped" and n.get("order_id"):
        n["order"] = {"id": n["order_id"]}
    if kind == "payout_released" and n.get("order_id"):
        n["order"] = {"id": n["order_id"]}
        if n.get("artwork_id"):
            art = await db.artworks.find_one({"id": n["artwork_id"]})
            if art:
                n["artwork"] = {"id": art["id"], "title": art["title"], "images": art.get("images", [])[:1]}
    if kind in ("order_confirmed", "artwork_sold", "new_review") and n.get("order_id"):
        n["order"] = {"id": n["order_id"]}
    if kind == "new_review" and n.get("artwork_id"):
        art = await db.artworks.find_one({"id": n["artwork_id"]})
        if art:
            n["artwork"] = {"id": art["id"], "title": art["title"], "images": art.get("images", [])[:1]}
    if kind == "new_follower" and n.get("follower_id"):
        f = await db.users.find_one({"id": n["follower_id"]})
        if f:
            n["other"] = {"id": f["id"], "name": f["name"]}
    return n


@router.get("")
async def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    cursor = db.notifications.find({"user_id": user["id"]}).sort("created_at", -1).limit(limit)
    return [await _enrich(n) for n in await cursor.to_list(limit)]


@router.get("/unread-count")
async def unread_count(user: dict = Depends(get_current_user)):
    n = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"count": n}


class MarkReq(BaseModel):
    ids: Optional[List[str]] = None  # if None, mark all


@router.post("/read")
async def mark_read(req: MarkReq, user: dict = Depends(get_current_user)):
    q = {"user_id": user["id"], "read": False}
    if req.ids:
        q["id"] = {"$in": req.ids}
    r = await db.notifications.update_many(q, {"$set": {"read": True, "read_at": now_iso()}})
    return {"updated": r.modified_count}


@router.delete("/{nid}")
async def delete_notif(nid: str, user: dict = Depends(get_current_user)):
    r = await db.notifications.delete_one({"id": nid, "user_id": user["id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"deleted": 1}
