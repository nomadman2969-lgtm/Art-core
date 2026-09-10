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
    if kind in ("outbid", "auction_won", "auction_sold", "auction_forfeited", "auction_cancelled", "auction_deadline_soon", "auction_ending", "watched_auction_leader", "auction_paid") and n.get("auction_id"):
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
    if kind in ("order_shipped", "dispute_opened", "dispute_resolved", "order_refunded", "payout_reversed") and n.get("order_id"):
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
    # New social kinds (comment reply, new comment, artwork share, post like/comment, mentions, DM)
    if kind in ("new_comment", "comment_reply", "artwork_shared",
                "mentioned_in_comment", "mentioned_in_post_comment", "mentioned_in_post",
                "post_liked", "post_comment", "new_message",
                "event_broadcast", "event_rsvp", "event_ticket_paid"):
        if n.get("from_user_id"):
            u = await db.users.find_one({"id": n["from_user_id"]})
            if u:
                n["other"] = {"id": u["id"], "name": u["name"]}
        if n.get("artwork_id"):
            art = await db.artworks.find_one({"id": n["artwork_id"]})
            if art:
                n["artwork"] = {"id": art["id"], "title": art["title"], "images": art.get("images", [])[:1]}
        if n.get("post_id"):
            p = await db.studio_posts.find_one({"id": n["post_id"]})
            if p:
                n["post"] = {"id": p["id"], "text": (p.get("text") or "")[:80], "image": p.get("image")}
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



# --- Preferences (mute categories) ---
DEFAULT_PREFS = {
    "dm": True,
    "bid": True,
    "offer": True,
    "follow": True,
    "commission": True,
    "mention": True,
    "post": True,
    "event": True,
}


def _prefs_for(row: Optional[dict]) -> dict:
    """Merge defaults with saved row (missing keys default to True)."""
    saved = (row or {}).get("categories") or {}
    return {k: bool(saved.get(k, DEFAULT_PREFS[k])) for k in DEFAULT_PREFS}


async def get_prefs(user_id: str) -> dict:
    row = await db.notification_prefs.find_one({"user_id": user_id})
    return _prefs_for(row)


# Maps notification kinds → category
KIND_TO_CATEGORY = {
    "new_message": "dm",
    "outbid": "bid", "auction_won": "bid", "auction_sold": "bid",
    "auction_paid": "bid", "auction_forfeited": "bid", "auction_cancelled": "bid",
    "auction_deadline_soon": "bid", "watched_auction_leader": "bid", "auction_ending": "bid",
    "offer_received": "offer", "offer_accept": "offer", "offer_decline": "offer",
    "offer_counter": "offer", "offer_accepted_by_buyer": "offer",
    "offer_withdrawn": "offer", "offer_paid": "offer", "offer_expired": "offer",
    "new_follower": "follow",
    "commission_request": "commission", "commission_accept": "commission",
    "commission_decline": "commission", "commission_counter": "commission",
    "commission_progress": "commission", "commission_delivered": "commission",
    "commission_approved": "commission", "commission_deposit": "commission",
    "commission_paid": "commission",
    "mentioned_in_comment": "mention", "mentioned_in_post_comment": "mention",
    "mentioned_in_post": "mention",
    "post_liked": "post", "post_comment": "post",
    "new_comment": "post", "comment_reply": "post", "artwork_shared": "post",
    "new_review": "post",
    "event_rsvp": "event", "event_cancelled": "event",
    "event_reminder": "event", "event_ticket_paid": "event",
    "event_waitlist_open": "event", "event_waitlist_joined": "event", "event_broadcast": "event",
    "report_opened": "system", "report_resolved": "system", "moderation_action": "system",
}


async def push_allowed(user_id: str, kind: str) -> bool:
    """Called from push helper to decide whether to fan out a web-push for a given notif kind."""
    cat = KIND_TO_CATEGORY.get(kind)
    if not cat:
        return True  # unknown categories always deliver
    prefs = await get_prefs(user_id)
    return prefs.get(cat, True)


@router.get("/prefs")
async def read_prefs(user: dict = Depends(get_current_user)):
    return await get_prefs(user["id"])


class PrefsReq(BaseModel):
    categories: dict  # {dm: bool, bid: bool, ...}


@router.patch("/prefs")
async def update_prefs(req: PrefsReq, user: dict = Depends(get_current_user)):
    clean = {k: bool(v) for k, v in req.categories.items() if k in DEFAULT_PREFS}
    await db.notification_prefs.update_one(
        {"user_id": user["id"]},
        {"$set": {"user_id": user["id"], "categories": clean, "updated_at": now_iso()}},
        upsert=True,
    )
    return await get_prefs(user["id"])
