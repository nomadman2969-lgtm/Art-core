"""Virtual Artist Studio: config, themes, posts, analytics, AI designer."""
import json
import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, get_optional_user, require_role

router = APIRouter(prefix="/api/studio", tags=["studio"])


# ---------- Themes ----------
THEMES = {
    "urban_graffiti": {
        "name": "Urban Graffiti",
        "bg_url": "https://images.unsplash.com/photo-1611063158871-7dd3ed4a2ac8?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA3MDB8MHwxfHNlYXJjaHwzfHxncmFmZml0aSUyMHN0cmVldCUyMGFydHxlbnwwfHx8fDE3ODYzOTAwMzl8MA&ixlib=rb-4.1.0&q=85",
        "accent": "#CCFF00", "secondary": "#FF4D4D",
        "text": "#FFFFFF", "surface": "rgba(10,10,12,0.85)",
        "vibe": "raw brick, neon paint drips, hand-tagged energy",
    },
    "luxury_gallery": {
        "name": "Luxury Gallery",
        "bg_url": "https://images.unsplash.com/photo-1553644446-9f8f2762ea42?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzR8MHwxfHNlYXJjaHwzfHxtb2Rlcm4lMjBhcnQlMjBnYWxsZXJ5fGVufDB8fHx8MTc4NjM5MDAzOXww&ixlib=rb-4.1.0&q=85",
        "accent": "#D4AF37", "secondary": "#FFFFFF",
        "text": "#FFFFFF", "surface": "rgba(20,20,20,0.75)",
        "vibe": "high-end white walls, museum lighting, sophisticated typography",
    },
    "darkroom": {
        "name": "Darkroom",
        "bg_url": None,
        "accent": "#FF4D4D", "secondary": "#CCFF00",
        "text": "#FFFFFF", "surface": "rgba(5,5,5,0.9)",
        "vibe": "pure black backdrop, dramatic single-source spotlights, cinematic",
    },
    "industrial": {
        "name": "Industrial",
        "bg_url": "https://images.unsplash.com/photo-1487452066049-a710f7296400?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA3MDB8MHwxfHNlYXJjaHwxfHxncmFmZml0aSUyMHN0cmVldCUyMGFydHxlbnwwfHx8fDE3ODYzOTAwMzl8MA&ixlib=rb-4.1.0&q=85",
        "accent": "#F5A623", "secondary": "#00E5FF",
        "text": "#FFFFFF", "surface": "rgba(15,15,17,0.85)",
        "vibe": "steel + concrete + warehouse lighting",
    },
    "digital": {
        "name": "Digital",
        "bg_url": None,
        "accent": "#00E5FF", "secondary": "#FF00FF",
        "text": "#FFFFFF", "surface": "rgba(5,10,20,0.85)",
        "vibe": "cyberpunk grid, neon glow, futuristic HUD interface",
    },
    "minimal": {
        "name": "Minimal",
        "bg_url": None,
        "accent": "#FFFFFF", "secondary": "#A1A1AA",
        "text": "#FFFFFF", "surface": "rgba(18,18,20,0.6)",
        "vibe": "ultra clean, negative space, no decoration",
    },
    "warm_studio": {
        "name": "Warm Studio",
        "bg_url": "https://images.unsplash.com/photo-1541753866388-0b3c701627d3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzR8MHwxfHNlYXJjaHwxfHxhcnRpc3QlMjBwYWludGluZyUyMHN0dWRpb3xlbnwwfHx8fDE3ODYzOTAwMzl8MA&ixlib=rb-4.1.0&q=85",
        "accent": "#F5A623", "secondary": "#FF6EC7",
        "text": "#FFFFFF", "surface": "rgba(28,20,15,0.85)",
        "vibe": "cozy studio, wooden textures, warm amber lighting",
    },
}

DEFAULT_SECTIONS = [
    {"id": "featured", "kind": "featured_works", "title": "Featured Works", "order": 0, "visible": True},
    {"id": "available", "kind": "available_now", "title": "Available Now", "order": 1, "visible": True},
    {"id": "auctions", "kind": "upcoming_auctions", "title": "Live Auctions", "order": 2, "visible": True},
    {"id": "feed", "kind": "feed", "title": "Studio Feed", "order": 3, "visible": True},
    {"id": "story", "kind": "story", "title": "My Story", "order": 4, "visible": True},
    {"id": "commission", "kind": "commission", "title": "Commission Me", "order": 5, "visible": True},
    {"id": "sold", "kind": "sold_works", "title": "Sold Works", "order": 6, "visible": True},
]


@router.get("/themes")
async def list_themes():
    return [{"id": k, **v} for k, v in THEMES.items()]


def default_config(artist_id: str) -> dict:
    return {
        "artist_id": artist_id,
        "theme": "urban_graffiti",
        "background": {"type": "theme", "value": None},  # theme | image | color | preset
        "lighting": {"preset": "gallery", "intensity": 70},  # gallery | spotlight | neon | warm | cool | ambient
        "accent_color": None,  # override theme accent
        "typography": "brutalist",  # brutalist | serif | mono | modern
        "sections": DEFAULT_SECTIONS,
        "artist_story": {
            "location": "", "style": "", "years_active": None,
            "influences": "", "education": "", "awards": "", "exhibitions": "",
            "website": "", "instagram": "", "twitter": "",
        },
        "custom_css_accent": None,
        "visits": 0,
        "views_by_artwork": {},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


async def _get_or_create_config(artist_id: str) -> dict:
    c = await db.studio_configs.find_one({"artist_id": artist_id})
    if c:
        return strip_mongo(c)
    cfg = default_config(artist_id)
    await db.studio_configs.insert_one(cfg)
    return strip_mongo(await db.studio_configs.find_one({"artist_id": artist_id}))


@router.get("/{artist_id}")
async def get_studio(artist_id: str, viewer: Optional[dict] = Depends(get_optional_user)):
    """Full public studio view: config + artist + artworks by section + rank + social + recent posts."""
    artist = await db.users.find_one({"id": artist_id, "role": {"$in": ["artist", "admin"]}})
    if not artist:
        raise HTTPException(404, "Artist not found")
    cfg = await _get_or_create_config(artist_id)
    # Pull artworks by role
    all_arts = await db.artworks.find({"artist_id": artist_id, "status": {"$in": ["live", "sold"]}}).sort("created_at", -1).to_list(500)
    all_arts = [strip_mongo(a) for a in all_arts]
    available = [a for a in all_arts if a["status"] == "live"]
    sold = [a for a in all_arts if a["status"] == "sold"]
    featured = [a for a in all_arts if a.get("featured")]
    # Auctions
    auctions_c = db.auctions.find({"seller_id": artist_id, "status": {"$in": ["live", "scheduled"]}}).sort("end_at", 1)
    auctions_raw = await auctions_c.to_list(20)
    auctions = []
    for au in auctions_raw:
        au = strip_mongo(au)
        art = next((a for a in all_arts if a["id"] == au["artwork_id"]), None)
        if art:
            au["artwork"] = {"id": art["id"], "title": art["title"], "images": art.get("images", [])}
        auctions.append(au)
    # Recent posts
    posts_c = db.studio_posts.find({"artist_id": artist_id}).sort([("pinned", -1), ("created_at", -1)]).limit(30)
    posts = [strip_mongo(p) for p in await posts_c.to_list(30)]
    # Followers
    followers = await db.follows.count_documents({"followed_id": artist_id})
    following = await db.follows.count_documents({"follower_id": artist_id})
    # Increment visit (skip self-views)
    if not viewer or viewer["id"] != artist_id:
        await db.studio_configs.update_one({"artist_id": artist_id}, {"$inc": {"visits": 1}})
    return {
        "artist": {
            "id": artist["id"], "name": artist["name"], "bio": artist.get("bio"),
            "cover_image": artist.get("cover_image"), "avatar": artist.get("avatar"),
        },
        "config": cfg,
        "artworks": {
            "all": all_arts, "available": available, "sold": sold, "featured": featured,
        },
        "auctions": auctions,
        "posts": posts,
        "social": {"followers": followers, "following": following},
    }


class StudioUpdate(BaseModel):
    theme: Optional[str] = None
    background: Optional[Dict[str, Any]] = None
    lighting: Optional[Dict[str, Any]] = None
    accent_color: Optional[str] = None
    typography: Optional[str] = None
    sections: Optional[List[Dict[str, Any]]] = None
    artist_story: Optional[Dict[str, Any]] = None


@router.patch("")
async def update_studio(req: StudioUpdate, user: dict = Depends(require_role("artist", "admin"))):
    await _get_or_create_config(user["id"])
    updates = {k: v for k, v in req.model_dump(exclude_none=True).items()}
    updates["updated_at"] = now_iso()
    await db.studio_configs.update_one({"artist_id": user["id"]}, {"$set": updates})
    return strip_mongo(await db.studio_configs.find_one({"artist_id": user["id"]}))


@router.get("/analytics/me")
async def analytics(user: dict = Depends(require_role("artist", "admin"))):
    cfg = await _get_or_create_config(user["id"])
    art_ids = [a["id"] for a in await db.artworks.find({"artist_id": user["id"]}, {"id": 1, "title": 1, "images": 1}).to_list(500)]
    total_likes = await db.likes.count_documents({"artwork_id": {"$in": art_ids}})
    total_comments = await db.comments.count_documents({"artwork_id": {"$in": art_ids}})
    followers = await db.follows.count_documents({"followed_id": user["id"]})
    sales = await db.artworks.count_documents({"artist_id": user["id"], "status": "sold"})
    revenue_docs = await db.orders.find({"artist_payouts.artist_id": user["id"]}).to_list(500)
    revenue = 0.0
    for o in revenue_docs:
        for p in o.get("artist_payouts", []):
            if p["artist_id"] == user["id"]:
                revenue += p["gross"]
    # top artworks by likes
    tops = []
    for aid in art_ids:
        lk = await db.likes.count_documents({"artwork_id": aid})
        if lk > 0:
            art = await db.artworks.find_one({"id": aid})
            tops.append({"id": aid, "title": art["title"], "images": art.get("images", []), "likes": lk})
    tops.sort(key=lambda x: x["likes"], reverse=True)
    return {
        "visits": cfg.get("visits", 0),
        "total_likes": total_likes,
        "total_comments": total_comments,
        "followers": followers,
        "sales": sales,
        "revenue": round(revenue, 2),
        "artworks_count": len(art_ids),
        "top_artworks": tops[:8],
    }


# ---------- AI Studio Designer ----------
class AIDesignReq(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)


AI_SYSTEM = """You are a virtual art studio designer for the 'Art Core' platform.

Given a natural language description from an artist, respond ONLY with a valid JSON object (no prose, no code fences) describing their studio configuration.

The JSON MUST have these exact keys:
{
  "theme": one of ["urban_graffiti","luxury_gallery","darkroom","industrial","digital","minimal","warm_studio"],
  "accent_color": a hex color like "#CCFF00" that fits the vibe,
  "lighting": {"preset": one of ["gallery","spotlight","neon","warm","cool","ambient"], "intensity": integer 20-100},
  "typography": one of ["brutalist","serif","mono","modern"],
  "section_titles": {
    "featured_works": string (max 30 chars),
    "available_now": string (max 30 chars),
    "sold_works": string (max 30 chars),
    "upcoming_auctions": string (max 30 chars),
    "story": string (max 30 chars),
    "commission": string (max 30 chars),
    "feed": string (max 30 chars)
  },
  "story_hint": a short (max 200 char) suggested bio line that matches the vibe
}

Pick the theme that best matches the requested vibe. Rename section titles to match the vibe (e.g. for graffiti: 'Featured Works' -> 'The Walls', 'Sold Works' -> 'Off the Streets').
Return ONLY the JSON."""


@router.post("/ai-design")
async def ai_design(req: AIDesignReq, user: dict = Depends(require_role("artist", "admin"))):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"studio-design-{user['id']}-{new_id()[:8]}",
            system_message=AI_SYSTEM,
        ).with_model("anthropic", "claude-sonnet-4-6")
        resp = await chat.send_message(UserMessage(text=req.prompt))
        text = resp if isinstance(resp, str) else str(resp)
        # strip potential code fences
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        cfg = json.loads(text)
        # validate keys
        if cfg.get("theme") not in THEMES:
            cfg["theme"] = "urban_graffiti"
        return {"prompt": req.prompt, "config": cfg}
    except Exception as e:
        raise HTTPException(500, f"AI design failed: {str(e)[:200]}")


# ---------- Studio Posts (social feed) ----------
class PostCreate(BaseModel):
    kind: str = "update"  # update | wip | studio_photo | announcement | auction | sold | commission
    text: str = Field(min_length=1, max_length=2000)
    image: Optional[str] = None  # storage path
    pinned: bool = False


posts_router = APIRouter(prefix="/api/posts", tags=["studio-posts"])


@posts_router.post("")
async def create_post(req: PostCreate, user: dict = Depends(require_role("artist", "admin"))):
    p = {
        "id": new_id(),
        "artist_id": user["id"],
        "artist_name": user["name"],
        "kind": req.kind, "text": req.text, "image": req.image,
        "pinned": req.pinned,
        "like_count": 0, "comment_count": 0,
        "created_at": now_iso(),
    }
    await db.studio_posts.insert_one(p)
    return strip_mongo(p)


@posts_router.get("")
async def list_posts(artist_id: str, limit: int = 30):
    cursor = db.studio_posts.find({"artist_id": artist_id}).sort([("pinned", -1), ("created_at", -1)]).limit(limit)
    return [strip_mongo(p) for p in await cursor.to_list(limit)]


@posts_router.delete("/{post_id}")
async def delete_post(post_id: str, user: dict = Depends(get_current_user)):
    p = await db.studio_posts.find_one({"id": post_id})
    if not p:
        raise HTTPException(404, "Not found")
    if p["artist_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not yours")
    await db.studio_posts.delete_one({"id": post_id})
    return {"ok": True}


class PinReq(BaseModel):
    pinned: bool


@posts_router.patch("/{post_id}/pin")
async def pin_post(post_id: str, req: PinReq, user: dict = Depends(get_current_user)):
    p = await db.studio_posts.find_one({"id": post_id})
    if not p or (p["artist_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "Not found")
    await db.studio_posts.update_one({"id": post_id}, {"$set": {"pinned": req.pinned}})
    return {"pinned": req.pinned}


@posts_router.post("/{post_id}/like")
async def like_post(post_id: str, user: dict = Depends(get_current_user)):
    existing = await db.post_likes.find_one({"post_id": post_id, "user_id": user["id"]})
    if existing:
        return {"liked": True, "already": True}
    await db.post_likes.insert_one({"id": new_id(), "post_id": post_id, "user_id": user["id"], "created_at": now_iso()})
    await db.studio_posts.update_one({"id": post_id}, {"$inc": {"like_count": 1}})
    return {"liked": True}


@posts_router.delete("/{post_id}/like")
async def unlike_post(post_id: str, user: dict = Depends(get_current_user)):
    r = await db.post_likes.delete_one({"post_id": post_id, "user_id": user["id"]})
    if r.deleted_count:
        await db.studio_posts.update_one({"id": post_id}, {"$inc": {"like_count": -1}})
    return {"liked": False}
