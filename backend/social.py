"""Social features: follows, likes, comments (with replies + mentions), shares, saves, home feed."""
import re
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, get_optional_user, public_user

router = APIRouter(prefix="/api", tags=["social"])

MENTION_RE = re.compile(r"@([a-zA-Z0-9_\-\.]{2,32})")


async def _resolve_mentions(text: str) -> List[dict]:
    """Find @handles in text, resolve to user IDs (matches by name/email prefix, case-insensitive)."""
    handles = list(set(MENTION_RE.findall(text or "")))
    if not handles:
        return []
    out = []
    for h in handles[:8]:
        h_l = h.lower()
        u = await db.users.find_one({
            "$or": [
                {"handle": h_l},
                {"name": {"$regex": f"^{re.escape(h)}$", "$options": "i"}},
                {"email": {"$regex": f"^{re.escape(h)}(@|$)", "$options": "i"}},
            ]
        })
        if u:
            out.append({"handle": h, "user_id": u["id"], "name": u["name"]})
    return out


async def _notify_mentions(mentions: List[dict], from_user: dict, kind: str, **extra):
    for m in mentions:
        if m["user_id"] == from_user["id"]:
            continue
        await db.notifications.insert_one({
            "id": new_id(), "user_id": m["user_id"], "kind": kind,
            "from_user_id": from_user["id"], "from_user_name": from_user["name"],
            "read": False, "created_at": now_iso(), **extra,
        })


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
    await db.notifications.insert_one({
        "id": new_id(), "user_id": user_id, "kind": "new_follower",
        "follower_id": me["id"], "read": False, "created_at": now_iso(),
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


# --- Comments (with nested replies + mentions) ---
class CommentReq(BaseModel):
    text: str = Field(min_length=1, max_length=800)
    parent_id: Optional[str] = None


@router.post("/artworks/{artwork_id}/comments")
async def add_comment(artwork_id: str, req: CommentReq, me: dict = Depends(get_current_user)):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    parent = None
    if req.parent_id:
        parent = await db.comments.find_one({"id": req.parent_id, "artwork_id": artwork_id})
        if not parent:
            raise HTTPException(404, "Parent comment not found")
    mentions = await _resolve_mentions(req.text)
    c = {
        "id": new_id(), "artwork_id": artwork_id, "user_id": me["id"],
        "user_name": me["name"], "text": req.text,
        "parent_id": req.parent_id,
        "mentions": mentions,
        "reply_count": 0,
        "created_at": now_iso(),
    }
    await db.comments.insert_one(c)
    if parent:
        await db.comments.update_one({"id": parent["id"]}, {"$inc": {"reply_count": 1}})
        # notify the parent's author (if not the same person)
        if parent["user_id"] != me["id"]:
            await db.notifications.insert_one({
                "id": new_id(), "user_id": parent["user_id"], "kind": "comment_reply",
                "artwork_id": artwork_id, "comment_id": c["id"], "from_user_id": me["id"], "from_user_name": me["name"],
                "read": False, "created_at": now_iso(),
            })
    else:
        # Top-level: notify the artwork's artist
        if art.get("artist_id") and art["artist_id"] != me["id"]:
            await db.notifications.insert_one({
                "id": new_id(), "user_id": art["artist_id"], "kind": "new_comment",
                "artwork_id": artwork_id, "comment_id": c["id"], "from_user_id": me["id"], "from_user_name": me["name"],
                "read": False, "created_at": now_iso(),
            })
    await _notify_mentions(mentions, me, "mentioned_in_comment", artwork_id=artwork_id, comment_id=c["id"])
    return strip_mongo(c)


@router.get("/artworks/{artwork_id}/comments")
async def list_comments(artwork_id: str):
    """Returns comments in threaded form: top-level, each with a `replies` array."""
    cursor = db.comments.find({"artwork_id": artwork_id}).sort("created_at", 1).limit(500)
    all_comments = [strip_mongo(c) for c in await cursor.to_list(500)]
    by_parent = {}
    top_level = []
    for c in all_comments:
        if c.get("parent_id"):
            by_parent.setdefault(c["parent_id"], []).append(c)
        else:
            top_level.append(c)
    for c in top_level:
        c["replies"] = by_parent.get(c["id"], [])
    top_level.sort(key=lambda c: c["created_at"], reverse=True)
    return top_level


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, me: dict = Depends(get_current_user)):
    c = await db.comments.find_one({"id": comment_id})
    if not c:
        raise HTTPException(404, "Not found")
    if c["user_id"] != me["id"] and me["role"] != "admin":
        raise HTTPException(403, "Not yours")
    await db.comments.delete_one({"id": comment_id})
    if c.get("parent_id"):
        await db.comments.update_one({"id": c["parent_id"]}, {"$inc": {"reply_count": -1}})
    # Cascade delete replies
    await db.comments.delete_many({"parent_id": comment_id})
    return {"ok": True}


# --- Shares ---
class ShareReq(BaseModel):
    target: Optional[str] = None  # copy_link | twitter | instagram | direct


@router.post("/artworks/{artwork_id}/share")
async def share_artwork(artwork_id: str, req: ShareReq, me: Optional[dict] = Depends(get_optional_user)):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    await db.shares.insert_one({
        "id": new_id(), "artwork_id": artwork_id, "user_id": me["id"] if me else None,
        "target": req.target or "copy_link", "created_at": now_iso(),
    })
    await db.artworks.update_one({"id": artwork_id}, {"$inc": {"share_count": 1}})
    # Notify artist (throttled: at most one notification per user per day)
    if me and art.get("artist_id") and art["artist_id"] != me["id"]:
        today = now_iso()[:10]
        existing = await db.notifications.find_one({
            "user_id": art["artist_id"], "kind": "artwork_shared",
            "artwork_id": artwork_id, "from_user_id": me["id"],
            "created_at": {"$gte": today},
        })
        if not existing:
            await db.notifications.insert_one({
                "id": new_id(), "user_id": art["artist_id"], "kind": "artwork_shared",
                "artwork_id": artwork_id, "from_user_id": me["id"], "from_user_name": me["name"],
                "target": req.target, "read": False, "created_at": now_iso(),
            })
    count = await db.shares.count_documents({"artwork_id": artwork_id})
    return {"shared": True, "count": count}


@router.get("/artworks/{artwork_id}/shares")
async def get_shares(artwork_id: str):
    return {"count": await db.shares.count_documents({"artwork_id": artwork_id})}


# --- Saves & Collections ---
class SaveReq(BaseModel):
    collection_id: Optional[str] = None  # if null, saves to "All Saved"


@router.post("/artworks/{artwork_id}/save")
async def save_artwork(artwork_id: str, req: SaveReq, me: dict = Depends(get_current_user)):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    col_id = req.collection_id
    if col_id:
        col = await db.collections.find_one({"id": col_id, "user_id": me["id"]})
        if not col:
            raise HTTPException(404, "Collection not found")
    existing = await db.saves.find_one({"user_id": me["id"], "artwork_id": artwork_id, "collection_id": col_id})
    if existing:
        return {"saved": True, "already": True}
    await db.saves.insert_one({
        "id": new_id(), "user_id": me["id"], "artwork_id": artwork_id,
        "collection_id": col_id, "created_at": now_iso(),
    })
    return {"saved": True}


@router.delete("/artworks/{artwork_id}/save")
async def unsave_artwork(artwork_id: str, collection_id: Optional[str] = None, me: dict = Depends(get_current_user)):
    q = {"user_id": me["id"], "artwork_id": artwork_id}
    if collection_id:
        q["collection_id"] = collection_id
    await db.saves.delete_many(q)
    return {"saved": False}


@router.get("/artworks/{artwork_id}/saved")
async def is_saved(artwork_id: str, me: dict = Depends(get_current_user)):
    saved = bool(await db.saves.find_one({"user_id": me["id"], "artwork_id": artwork_id}))
    return {"saved": saved}


class CollectionReq(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: Optional[str] = Field(default=None, max_length=300)
    is_private: bool = False


@router.post("/collections")
async def create_collection(req: CollectionReq, me: dict = Depends(get_current_user)):
    c = {
        "id": new_id(), "user_id": me["id"],
        "name": req.name, "description": req.description,
        "is_private": req.is_private,
        "created_at": now_iso(),
    }
    await db.collections.insert_one(c)
    return strip_mongo(c)


@router.get("/collections/mine")
async def my_collections(me: dict = Depends(get_current_user)):
    cursor = db.collections.find({"user_id": me["id"]}).sort("created_at", -1).limit(100)
    cols = [strip_mongo(c) for c in await cursor.to_list(100)]
    for c in cols:
        c["item_count"] = await db.saves.count_documents({"user_id": me["id"], "collection_id": c["id"]})
        # Cover images: first 3 artworks
        saves = await db.saves.find({"user_id": me["id"], "collection_id": c["id"]}).sort("created_at", -1).limit(3).to_list(3)
        covers = []
        for s in saves:
            art = await db.artworks.find_one({"id": s["artwork_id"]}, {"images": 1})
            if art and art.get("images"):
                covers.append(art["images"][0])
        c["covers"] = covers
    # Add "All Saved" pseudo-collection first
    total = await db.saves.count_documents({"user_id": me["id"]})
    all_covers_saves = await db.saves.find({"user_id": me["id"]}).sort("created_at", -1).limit(3).to_list(3)
    all_covers = []
    for s in all_covers_saves:
        art = await db.artworks.find_one({"id": s["artwork_id"]}, {"images": 1})
        if art and art.get("images"):
            all_covers.append(art["images"][0])
    return [{"id": "all", "name": "All Saved", "is_all": True, "item_count": total, "covers": all_covers, "created_at": None}] + cols


@router.get("/collections/{collection_id}")
async def get_collection(collection_id: str, me: dict = Depends(get_current_user)):
    if collection_id == "all":
        saves = await db.saves.find({"user_id": me["id"]}).sort("created_at", -1).limit(500).to_list(500)
        col = {"id": "all", "name": "All Saved", "is_all": True, "user_id": me["id"]}
    else:
        col = await db.collections.find_one({"id": collection_id})
        if not col:
            raise HTTPException(404, "Not found")
        if col["user_id"] != me["id"] and col.get("is_private"):
            raise HTTPException(403, "Private")
        saves = await db.saves.find({"user_id": col["user_id"], "collection_id": collection_id}).sort("created_at", -1).limit(500).to_list(500)
    items = []
    for s in saves:
        art = await db.artworks.find_one({"id": s["artwork_id"]})
        if art:
            art = strip_mongo(art)
            artist = await db.users.find_one({"id": art.get("artist_id")})
            if artist:
                art["artist"] = {"id": artist["id"], "name": artist["name"]}
            items.append(art)
    return {"collection": strip_mongo(col), "items": items}


@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str, me: dict = Depends(get_current_user)):
    col = await db.collections.find_one({"id": collection_id})
    if not col:
        raise HTTPException(404, "Not found")
    if col["user_id"] != me["id"]:
        raise HTTPException(403, "Not yours")
    await db.collections.delete_one({"id": collection_id})
    # Saves under this collection become uncategorized (collection_id -> null)
    await db.saves.update_many({"user_id": me["id"], "collection_id": collection_id}, {"$set": {"collection_id": None}})
    return {"ok": True}


# --- Home feed (personalized timeline) ---
@router.get("/feed/home")
async def home_feed(
    limit: int = 40,
    kinds: Optional[str] = None,   # csv of post kinds (wip,announcement...) — also 'artwork' includes new artworks, 'post' includes all post kinds
    type: str = "all",              # all | post | artwork
    me: dict = Depends(get_current_user),
):
    """Timeline of posts + new artworks from artists the user follows."""
    limit = max(1, min(limit, 100))
    follows = await db.follows.find({"follower_id": me["id"]}).to_list(500)
    followed_ids = [f["followed_id"] for f in follows]
    items = []
    include_posts = type in ("all", "post")
    include_artworks = type in ("all", "artwork")
    # If kinds is provided, treat 'artwork' as a special token for new-artwork items
    kind_set = None
    if kinds:
        kind_set = set(k.strip() for k in kinds.split(",") if k.strip())
        if kind_set:
            include_artworks = "artwork" in kind_set
            include_posts = any(k != "artwork" for k in kind_set)
    if followed_ids and include_posts:
        post_filter = {"artist_id": {"$in": followed_ids}}
        if kind_set:
            post_kinds = [k for k in kind_set if k != "artwork"]
            if post_kinds:
                post_filter["kind"] = {"$in": post_kinds}
        async for p in db.studio_posts.find(post_filter).sort("created_at", -1).limit(limit):
            p = strip_mongo(p)
            artist = await db.users.find_one({"id": p["artist_id"]})
            if artist:
                p["artist"] = {"id": artist["id"], "name": artist["name"]}
            p["timeline_kind"] = "post"
            p["timeline_at"] = p["created_at"]
            p["like_count"] = await db.post_likes.count_documents({"post_id": p["id"]})
            p["comment_count"] = await db.post_comments.count_documents({"post_id": p["id"]})
            p["liked"] = bool(await db.post_likes.find_one({"post_id": p["id"], "user_id": me["id"]}))
            items.append(p)
    if followed_ids and include_artworks:
        async for a in db.artworks.find({"artist_id": {"$in": followed_ids}, "status": {"$in": ["live", "sold"]}}).sort("created_at", -1).limit(limit):
            a = strip_mongo(a)
            artist = await db.users.find_one({"id": a["artist_id"]})
            if artist:
                a["artist"] = {"id": artist["id"], "name": artist["name"]}
            a["timeline_kind"] = "artwork"
            a["timeline_at"] = a["created_at"]
            a["like_count"] = await db.likes.count_documents({"artwork_id": a["id"]})
            a["comment_count"] = await db.comments.count_documents({"artwork_id": a["id"]})
            a["liked"] = bool(await db.likes.find_one({"user_id": me["id"], "artwork_id": a["id"]}))
            items.append(a)
    items.sort(key=lambda i: i.get("timeline_at") or "", reverse=True)
    items = items[:limit]
    return {"following_count": len(followed_ids), "items": items}


# --- Mention autocomplete ---
@router.get("/users/search")
async def users_search(q: str = "", limit: int = 8, me: Optional[dict] = Depends(get_optional_user)):
    """Fuzzy-search users by name for @mention autocomplete."""
    q = (q or "").strip()
    if not q or len(q) < 1:
        return []
    limit = max(1, min(limit, 20))
    rx = re.compile(re.escape(q), re.IGNORECASE)
    cursor = db.users.find({
        "$or": [
            {"name": rx},
            {"handle": rx},
            {"email": {"$regex": f"^{re.escape(q)}", "$options": "i"}},
        ],
    }).limit(limit * 2)
    out = []
    seen = set()
    for u in await cursor.to_list(limit * 2):
        if u["id"] in seen or (me and u["id"] == me["id"]):
            continue
        seen.add(u["id"])
        out.append({
            "id": u["id"],
            "name": u["name"],
            "role": u.get("role"),
            "bio": (u.get("bio") or "")[:100],
        })
        if len(out) >= limit:
            break
    # Prioritize artists (they're the main mention targets)
    out.sort(key=lambda u: (0 if u.get("role") == "artist" else 1, u["name"].lower()))
    return out


# --- Post engagement (likes + comments on studio_posts) ---
@router.post("/posts/{post_id}/like")
async def like_post(post_id: str, me: dict = Depends(get_current_user)):
    p = await db.studio_posts.find_one({"id": post_id})
    if not p:
        raise HTTPException(404, "Not found")
    existing = await db.post_likes.find_one({"post_id": post_id, "user_id": me["id"]})
    if existing:
        return {"liked": True, "already": True}
    await db.post_likes.insert_one({
        "id": new_id(), "post_id": post_id, "user_id": me["id"], "created_at": now_iso(),
    })
    await db.studio_posts.update_one({"id": post_id}, {"$inc": {"like_count": 1}})
    if p["artist_id"] != me["id"]:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": p["artist_id"], "kind": "post_liked",
            "post_id": post_id, "from_user_id": me["id"], "from_user_name": me["name"],
            "read": False, "created_at": now_iso(),
        })
    return {"liked": True}


@router.delete("/posts/{post_id}/like")
async def unlike_post(post_id: str, me: dict = Depends(get_current_user)):
    r = await db.post_likes.delete_many({"post_id": post_id, "user_id": me["id"]})
    if r.deleted_count:
        await db.studio_posts.update_one({"id": post_id}, {"$inc": {"like_count": -1}})
    return {"liked": False}


class PostCommentReq(BaseModel):
    text: str = Field(min_length=1, max_length=800)


@router.post("/posts/{post_id}/comments")
async def add_post_comment(post_id: str, req: PostCommentReq, me: dict = Depends(get_current_user)):
    p = await db.studio_posts.find_one({"id": post_id})
    if not p:
        raise HTTPException(404, "Not found")
    mentions = await _resolve_mentions(req.text)
    c = {
        "id": new_id(), "post_id": post_id, "user_id": me["id"],
        "user_name": me["name"], "text": req.text,
        "mentions": mentions,
        "created_at": now_iso(),
    }
    await db.post_comments.insert_one(c)
    await db.studio_posts.update_one({"id": post_id}, {"$inc": {"comment_count": 1}})
    if p["artist_id"] != me["id"]:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": p["artist_id"], "kind": "post_comment",
            "post_id": post_id, "comment_id": c["id"], "from_user_id": me["id"], "from_user_name": me["name"],
            "read": False, "created_at": now_iso(),
        })
    await _notify_mentions(mentions, me, "mentioned_in_post_comment", post_id=post_id, comment_id=c["id"])
    return strip_mongo(c)


@router.get("/posts/{post_id}/comments")
async def list_post_comments(post_id: str):
    cursor = db.post_comments.find({"post_id": post_id}).sort("created_at", 1).limit(200)
    return [strip_mongo(c) for c in await cursor.to_list(200)]


# --- Following / Followers lists ---
@router.get("/users/{user_id}/following")
async def get_following(user_id: str, me: Optional[dict] = Depends(get_optional_user)):
    follows = await db.follows.find({"follower_id": user_id}).sort("created_at", -1).to_list(500)
    out = []
    for f in follows:
        u = await db.users.find_one({"id": f["followed_id"]})
        if u:
            item = public_user(u)
            if me:
                item["is_following"] = bool(await db.follows.find_one({"follower_id": me["id"], "followed_id": u["id"]}))
            out.append(item)
    return out


@router.get("/users/{user_id}/followers")
async def get_followers(user_id: str, me: Optional[dict] = Depends(get_optional_user)):
    follows = await db.follows.find({"followed_id": user_id}).sort("created_at", -1).to_list(500)
    out = []
    for f in follows:
        u = await db.users.find_one({"id": f["follower_id"]})
        if u:
            item = public_user(u)
            if me:
                item["is_following"] = bool(await db.follows.find_one({"follower_id": me["id"], "followed_id": u["id"]}))
            out.append(item)
    return out


# --- Explore feed (existing, extended with share/save state) ---
@router.get("/feed")
async def explore_feed(limit: int = 60, me: Optional[dict] = Depends(get_optional_user)):
    limit = max(1, min(limit, 200))
    cursor = db.artworks.find({"status": {"$in": ["live", "sold"]}}).sort("created_at", -1).limit(limit)
    out = []
    for a in await cursor.to_list(limit):
        a = strip_mongo(a)
        artist = await db.users.find_one({"id": a.get("artist_id")})
        if artist:
            a["artist"] = {"id": artist["id"], "name": artist["name"]}
        a["like_count"] = await db.likes.count_documents({"artwork_id": a["id"]})
        a["comment_count"] = await db.comments.count_documents({"artwork_id": a["id"]})
        a["share_count"] = await db.shares.count_documents({"artwork_id": a["id"]})
        if me:
            a["liked"] = bool(await db.likes.find_one({"user_id": me["id"], "artwork_id": a["id"]}))
            a["saved"] = bool(await db.saves.find_one({"user_id": me["id"], "artwork_id": a["id"]}))
        out.append(a)
    return out
