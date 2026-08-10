"""Social features: follows, likes, comments."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, get_optional_user, public_user

router = APIRouter(prefix="/api", tags=["social"])


# --- Follows ---
@router.post("/users/{user_id}/follow")
async def follow_user(user_id: str, me: dict = Depends(get_current_user)):
    if user_id == me["id"]:
        raise HTTPException(400, "Cannot follow yourself")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "User not found")
    existing = await db.follows.find_one({"follower_id": me["id"], "followed_id": user_id})
    if existing:
        return {"ok": True, "already": True}
    await db.follows.insert_one({
        "id": new_id(), "follower_id": me["id"], "followed_id": user_id, "created_at": now_iso(),
    })
    return {"ok": True}


@router.delete("/users/{user_id}/follow")
async def unfollow_user(user_id: str, me: dict = Depends(get_current_user)):
    await db.follows.delete_many({"follower_id": me["id"], "followed_id": user_id})
    return {"ok": True}


@router.get("/users/{user_id}/social")
async def user_social(user_id: str, me: Optional[dict] = Depends(get_optional_user)):
    followers = await db.follows.count_documents({"followed_id": user_id})
    following = await db.follows.count_documents({"follower_id": user_id})
    is_following = False
    if me:
        is_following = bool(await db.follows.find_one({"follower_id": me["id"], "followed_id": user_id}))
    return {"followers": followers, "following": following, "is_following": is_following}


# --- Likes ---
@router.post("/artworks/{artwork_id}/like")
async def like_artwork(artwork_id: str, me: dict = Depends(get_current_user)):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    existing = await db.likes.find_one({"user_id": me["id"], "artwork_id": artwork_id})
    if existing:
        return {"liked": True, "already": True}
    await db.likes.insert_one({
        "id": new_id(), "user_id": me["id"], "artwork_id": artwork_id, "created_at": now_iso(),
    })
    return {"liked": True}


@router.delete("/artworks/{artwork_id}/like")
async def unlike_artwork(artwork_id: str, me: dict = Depends(get_current_user)):
    await db.likes.delete_many({"user_id": me["id"], "artwork_id": artwork_id})
    return {"liked": False}


@router.get("/artworks/{artwork_id}/likes")
async def get_likes(artwork_id: str, me: Optional[dict] = Depends(get_optional_user)):
    count = await db.likes.count_documents({"artwork_id": artwork_id})
    liked = False
    if me:
        liked = bool(await db.likes.find_one({"user_id": me["id"], "artwork_id": artwork_id}))
    return {"count": count, "liked": liked}


# --- Comments ---
class CommentReq(BaseModel):
    text: str = Field(min_length=1, max_length=800)


@router.post("/artworks/{artwork_id}/comments")
async def add_comment(artwork_id: str, req: CommentReq, me: dict = Depends(get_current_user)):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    c = {
        "id": new_id(), "artwork_id": artwork_id, "user_id": me["id"],
        "user_name": me["name"], "text": req.text, "created_at": now_iso(),
    }
    await db.comments.insert_one(c)
    return strip_mongo(c)


@router.get("/artworks/{artwork_id}/comments")
async def list_comments(artwork_id: str):
    cursor = db.comments.find({"artwork_id": artwork_id}).sort("created_at", -1).limit(100)
    return [strip_mongo(c) for c in await cursor.to_list(100)]


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, me: dict = Depends(get_current_user)):
    c = await db.comments.find_one({"id": comment_id})
    if not c:
        raise HTTPException(404, "Not found")
    if c["user_id"] != me["id"] and me["role"] != "admin":
        raise HTTPException(403, "Not yours")
    await db.comments.delete_one({"id": comment_id})
    return {"ok": True}


# --- Feed (explore) ---
@router.get("/feed")
async def explore_feed(limit: int = 60, me: Optional[dict] = Depends(get_optional_user)):
    """Explore feed — mix of recent + featured artworks, enriched with artist + like counts."""
    cursor = db.artworks.find({"status": {"$in": ["live", "sold"]}}).sort("created_at", -1).limit(limit)
    out = []
    for a in await cursor.to_list(limit):
        a = strip_mongo(a)
        artist = await db.users.find_one({"id": a.get("artist_id")})
        if artist:
            a["artist"] = {"id": artist["id"], "name": artist["name"]}
        a["like_count"] = await db.likes.count_documents({"artwork_id": a["id"]})
        a["comment_count"] = await db.comments.count_documents({"artwork_id": a["id"]})
        if me:
            a["liked"] = bool(await db.likes.find_one({"user_id": me["id"], "artwork_id": a["id"]}))
        out.append(a)
    return out
