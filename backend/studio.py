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
        "default_texture": "graffiti",
    },
    "luxury_gallery": {
        "name": "Luxury Gallery",
        "bg_url": "https://images.unsplash.com/photo-1553644446-9f8f2762ea42?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzR8MHwxfHNlYXJjaHwzfHxtb2Rlcm4lMjBhcnQlMjBnYWxsZXJ5fGVufDB8fHx8MTc4NjM5MDAzOXww&ixlib=rb-4.1.0&q=85",
        "accent": "#D4AF37", "secondary": "#FFFFFF",
        "text": "#FFFFFF", "surface": "rgba(20,20,20,0.75)",
        "vibe": "high-end white walls, museum lighting, sophisticated typography",
        "default_texture": "none",
    },
    "dark_gallery": {
        "name": "Dark Gallery",
        "bg_url": None,
        "accent": "#FF4D4D", "secondary": "#CCFF00",
        "text": "#FFFFFF", "surface": "rgba(5,5,5,0.9)",
        "vibe": "pure black backdrop, dramatic single-source spotlights, cinematic",
        "default_texture": "none",
    },
    "industrial": {
        "name": "Industrial",
        "bg_url": "https://images.unsplash.com/photo-1487452066049-a710f7296400?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA3MDB8MHwxfHNlYXJjaHwxfHxncmFmZml0aSUyMHN0cmVldCUyMGFydHxlbnwwfHx8fDE3ODYzOTAwMzl8MA&ixlib=rb-4.1.0&q=85",
        "accent": "#F5A623", "secondary": "#00E5FF",
        "text": "#FFFFFF", "surface": "rgba(15,15,17,0.85)",
        "vibe": "steel + concrete + warehouse lighting",
        "default_texture": "concrete",
    },
    "neon_digital": {
        "name": "Neon Digital",
        "bg_url": None,
        "accent": "#00E5FF", "secondary": "#FF00FF",
        "text": "#FFFFFF", "surface": "rgba(5,10,20,0.85)",
        "vibe": "cyberpunk grid, neon glow, futuristic HUD interface",
        "default_texture": "grid",
    },
    "minimal": {
        "name": "Minimal",
        "bg_url": None,
        "accent": "#FFFFFF", "secondary": "#A1A1AA",
        "text": "#FFFFFF", "surface": "rgba(18,18,20,0.6)",
        "vibe": "ultra clean, negative space, no decoration",
        "default_texture": "none",
    },
    "custom": {
        "name": "Custom",
        "bg_url": None,
        "accent": "#CCFF00", "secondary": "#7C3AED",
        "text": "#FFFFFF", "surface": "rgba(10,10,12,0.85)",
        "vibe": "your rules — pick your own background, textures, accents",
        "default_texture": "none",
    },
}

# Legacy theme aliases → new IDs (for backward compatibility with existing studios)
THEME_ALIASES = {
    "darkroom": "dark_gallery",
    "digital": "neon_digital",
    "warm_studio": "industrial",
}

TEXTURES = ["none", "graffiti", "brick", "concrete", "grid", "noise", "paper"]
LAYOUTS = ["grid", "masonry", "salon", "showcase", "carousel"]
SECTION_KINDS_ALL = [
    "featured_works", "available_now", "sold_works", "upcoming_auctions",
    "feed", "story", "commission", "custom",
    # New rich blocks
    "announcement", "text_block", "button_cta", "image_block",
]

# ---------- Starter templates ----------
TEMPLATES = {
    "emerging_artist": {
        "name": "Emerging Artist",
        "description": "Bold and personal. Story-forward layout for artists getting started.",
        "vibe": "Fresh · Personal · Story-first",
        "config": {
            "theme": "urban_graffiti",
            "accent_color": "#CCFF00",
            "background": {"type": "theme", "value": None, "texture": "graffiti", "texture_opacity": 30},
            "lighting": {"preset": "gallery", "intensity": 70},
            "typography": "brutalist",
            "commission_open": True,
            "commission_blurb": "New collectors welcome — DM me anything, no ask is too small.",
            "sections": [
                {"id": "t-announce", "kind": "announcement", "title": "Studio Update", "order": 0, "visible": True,
                 "body": "Welcome to my studio. New drops every month — follow to catch them first.", "variant": "info"},
                {"id": "t-featured", "kind": "featured_works", "title": "New Work", "order": 1, "visible": True, "layout": "showcase"},
                {"id": "t-available", "kind": "available_now", "title": "Available Now", "order": 2, "visible": True, "layout": "grid"},
                {"id": "t-story", "kind": "story", "title": "About Me", "order": 3, "visible": True},
                {"id": "t-feed", "kind": "feed", "title": "Studio Journal", "order": 4, "visible": True},
                {"id": "t-comm", "kind": "commission", "title": "Commission Me", "order": 5, "visible": True},
                {"id": "t-sold", "kind": "sold_works", "title": "In Private Collections", "order": 6, "visible": True, "layout": "grid"},
            ],
        },
    },
    "gallery_owner": {
        "name": "Gallery Owner",
        "description": "Museum-grade presentation. Curator's voice, salon-wall showcase.",
        "vibe": "Museum · Curated · Salon Wall",
        "config": {
            "theme": "luxury_gallery",
            "accent_color": "#D4AF37",
            "background": {"type": "theme", "value": None, "texture": "none", "texture_opacity": 15},
            "lighting": {"preset": "spotlight", "intensity": 85},
            "typography": "serif",
            "commission_open": False,
            "commission_blurb": "Commissions by invitation only. Approach through the gallery.",
            "sections": [
                {"id": "t-featured", "kind": "featured_works", "title": "Curator's Selection", "order": 0, "visible": True, "layout": "salon"},
                {"id": "t-auctions", "kind": "upcoming_auctions", "title": "Now on the Block", "order": 1, "visible": True},
                {"id": "t-available", "kind": "available_now", "title": "The Collection", "order": 2, "visible": True, "layout": "masonry"},
                {"id": "t-story", "kind": "story", "title": "The Gallery", "order": 3, "visible": True},
                {"id": "t-sold", "kind": "sold_works", "title": "Placed Works", "order": 4, "visible": True, "layout": "grid"},
                {"id": "t-feed", "kind": "feed", "title": "News & Events", "order": 5, "visible": True},
            ],
        },
    },
    "print_shop": {
        "name": "Print Shop",
        "description": "High-volume, product-first. Carousels, big CTAs, bright energy.",
        "vibe": "Retail · High-volume · Bold CTAs",
        "config": {
            "theme": "neon_digital",
            "accent_color": "#00E5FF",
            "background": {"type": "theme", "value": None, "texture": "grid", "texture_opacity": 20},
            "lighting": {"preset": "neon", "intensity": 90},
            "typography": "modern",
            "commission_open": True,
            "commission_blurb": "Custom prints from $25. Bulk pricing available — let's talk.",
            "sections": [
                {"id": "t-cta", "kind": "button_cta", "title": "Shop the Latest", "order": 0, "visible": True,
                 "body": "New drops every Friday. Free shipping on orders over $75.",
                 "button_text": "Browse New Prints", "button_link": "#available"},
                {"id": "t-featured", "kind": "featured_works", "title": "Best Sellers", "order": 1, "visible": True, "layout": "carousel"},
                {"id": "t-available", "kind": "available_now", "title": "In Stock Now", "order": 2, "visible": True, "layout": "grid"},
                {"id": "t-announce", "kind": "announcement", "title": "Studio News", "order": 3, "visible": True,
                 "body": "Free shipping this month on all orders over $75.", "variant": "success"},
                {"id": "t-comm", "kind": "commission", "title": "Custom Orders", "order": 4, "visible": True},
                {"id": "t-story", "kind": "story", "title": "The Shop", "order": 5, "visible": True},
            ],
        },
    },
    "dark_solo": {
        "name": "Dark Solo Show",
        "description": "One artist, cinematic. Dark, single-showcase focus.",
        "vibe": "Cinematic · Focused · Minimal",
        "config": {
            "theme": "dark_gallery",
            "accent_color": "#FF4D4D",
            "background": {"type": "theme", "value": None, "texture": "noise", "texture_opacity": 15},
            "lighting": {"preset": "spotlight", "intensity": 60},
            "typography": "brutalist",
            "commission_open": True,
            "commission_blurb": "Selective commissions. One at a time, done right.",
            "sections": [
                {"id": "t-featured", "kind": "featured_works", "title": "The Piece", "order": 0, "visible": True, "layout": "showcase"},
                {"id": "t-story", "kind": "story", "title": "The Artist", "order": 1, "visible": True},
                {"id": "t-available", "kind": "available_now", "title": "Other Works", "order": 2, "visible": True, "layout": "masonry"},
                {"id": "t-comm", "kind": "commission", "title": "Commission", "order": 3, "visible": True},
                {"id": "t-feed", "kind": "feed", "title": "Notes", "order": 4, "visible": True},
            ],
        },
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


# Note: /templates and /apply-template must be defined BEFORE any /{artist_id} route
# to prevent path matching issues in FastAPI's router.
@router.get("/themes")
async def list_themes():
    return [{"id": k, **v} for k, v in THEMES.items()]


@router.get("/templates")
async def list_templates():
    return [{"id": k, "name": v["name"], "description": v["description"], "vibe": v["vibe"],
             "theme": v["config"]["theme"], "accent": v["config"]["accent_color"]}
            for k, v in TEMPLATES.items()]


def default_config(artist_id: str) -> dict:
    return {
        "artist_id": artist_id,
        "theme": "urban_graffiti",
        "background": {
            "type": "theme",   # theme | image | color
            "value": None,
            "texture": "graffiti",  # graffiti | brick | concrete | grid | noise | paper | none
            "texture_opacity": 25,  # 0-100
        },
        "lighting": {"preset": "gallery", "intensity": 70},
        "accent_color": None,
        "typography": "brutalist",
        "sections": DEFAULT_SECTIONS,
        "featured_artwork_ids": [],  # explicit override for featured_works section
        "commission_open": True,  # commission availability toggle
        "commission_blurb": None,  # custom copy on commission block
        "artist_story": {
            "location": "", "style": "", "years_active": None,
            "influences": "", "education": "", "awards": "", "exhibitions": "",
            "website": "", "instagram": "", "twitter": "",
        },
        "custom_css_accent": None,
        "visits": 0,
        "views_by_artwork": {},
        "draft": None,  # holds unpublished changes
        "published_at": now_iso(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def _migrate_theme(cfg: dict) -> dict:
    """Rewrite legacy theme IDs to their new names on-the-fly."""
    if cfg.get("theme") in THEME_ALIASES:
        cfg["theme"] = THEME_ALIASES[cfg["theme"]]
    d = cfg.get("draft") or {}
    if isinstance(d, dict) and d.get("theme") in THEME_ALIASES:
        d["theme"] = THEME_ALIASES[d["theme"]]
        cfg["draft"] = d
    return cfg


async def _get_or_create_config(artist_id: str) -> dict:
    c = await db.studio_configs.find_one({"artist_id": artist_id})
    if c:
        migrated = _migrate_theme(strip_mongo(c))
        # Persist migration + backfill new fields once
        needs_save = migrated.get("theme") != c.get("theme")
        for k, v in [("featured_artwork_ids", []), ("commission_open", True), ("commission_blurb", None), ("draft", None), ("published_at", c.get("updated_at"))]:
            if k not in c:
                migrated[k] = v
                needs_save = True
        if "texture" not in (c.get("background") or {}):
            migrated["background"] = {**(c.get("background") or {"type": "theme"}), "texture": "none", "texture_opacity": 25}
            needs_save = True
        if needs_save:
            await db.studio_configs.update_one({"artist_id": artist_id}, {"$set": migrated})
        return migrated
    cfg = default_config(artist_id)
    await db.studio_configs.insert_one(cfg)
    return strip_mongo(await db.studio_configs.find_one({"artist_id": artist_id}))


@router.get("/{artist_id}")
async def get_studio(artist_id: str, preview: bool = False, viewer: Optional[dict] = Depends(get_optional_user)):
    """Public studio view. If preview=true and viewer is the owner, apply their unpublished draft."""
    artist = await db.users.find_one({"id": artist_id, "role": {"$in": ["artist", "admin"]}})
    if not artist:
        raise HTTPException(404, "Artist not found")
    cfg = await _get_or_create_config(artist_id)
    is_owner = viewer and viewer["id"] == artist_id
    if preview and is_owner and cfg.get("draft"):
        # Merge draft over published fields (only known keys)
        draft = cfg["draft"]
        for k in ("theme", "background", "lighting", "accent_color", "typography", "sections",
                  "featured_artwork_ids", "commission_open", "commission_blurb", "artist_story"):
            if k in draft:
                cfg[k] = draft[k]
        cfg["is_preview"] = True
    else:
        cfg["is_preview"] = False
    cfg["has_draft"] = bool(cfg.get("draft"))
    # Pull artworks by role
    all_arts = await db.artworks.find({"artist_id": artist_id, "status": {"$in": ["live", "sold"]}}).sort("created_at", -1).to_list(500)
    all_arts = [strip_mongo(a) for a in all_arts]
    available = [a for a in all_arts if a["status"] == "live"]
    sold = [a for a in all_arts if a["status"] == "sold"]
    # Featured: explicit picks first, else artworks flagged featured=True
    picks = cfg.get("featured_artwork_ids") or []
    if picks:
        picks_set = set(picks)
        # preserve chosen order
        by_id = {a["id"]: a for a in all_arts}
        featured = [by_id[pid] for pid in picks if pid in by_id]
    else:
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
    posts_c = db.studio_posts.find({"artist_id": artist_id, "hidden": {"$ne": True}}).sort([("pinned", -1), ("created_at", -1)]).limit(30)
    posts = [strip_mongo(p) for p in await posts_c.to_list(30)]
    # Followers
    followers = await db.follows.count_documents({"followed_id": artist_id})
    following = await db.follows.count_documents({"follower_id": artist_id})
    # Increment visit (skip self-views)
    if not viewer or viewer["id"] != artist_id:
        await db.studio_configs.update_one({"artist_id": artist_id}, {"$inc": {"visits": 1}})
        await db.studio_visits.insert_one({"id": new_id(), "artist_id": artist_id, "viewer_id": viewer["id"] if viewer else None, "created_at": now_iso()})
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
    featured_artwork_ids: Optional[List[str]] = None
    commission_open: Optional[bool] = None
    commission_blurb: Optional[str] = None
    publish: bool = False  # if true, write straight to live (skip draft)


def _validate_section(s: dict) -> dict:
    """Sanitize a section dict."""
    kind = s.get("kind", "custom")
    if kind not in SECTION_KINDS_ALL:
        raise HTTPException(400, f"Unknown section kind: {kind}")
    out = {
        "id": s.get("id") or new_id(),
        "kind": kind,
        "title": (s.get("title") or "Section")[:60],
        "order": int(s.get("order", 0)),
        "visible": bool(s.get("visible", True)),
    }
    # Optional layout (grid | masonry | salon | showcase | carousel)
    if kind in ("featured_works", "available_now", "sold_works"):
        layout = s.get("layout", "grid")
        if layout not in LAYOUTS:
            layout = "grid"
        out["layout"] = layout
    # Rich block payloads
    if kind in ("custom", "text_block", "announcement"):
        out["body"] = (s.get("body") or "")[:4000]
    if kind == "announcement":
        out["variant"] = s.get("variant", "info")  # info | success | warning
    if kind == "button_cta":
        out["button_text"] = (s.get("button_text") or "Click")[:60]
        out["button_link"] = (s.get("button_link") or "#")[:400]
        out["body"] = (s.get("body") or "")[:2000]
    if kind == "image_block":
        out["image"] = s.get("image")
        out["caption"] = (s.get("caption") or "")[:400]
        out["body"] = (s.get("body") or "")[:2000]
    # Optional background override per section
    if s.get("background_color"):
        out["background_color"] = s["background_color"][:32]
    return out


def _sanitize_patch(patch: dict) -> dict:
    if "sections" in patch and patch["sections"] is not None:
        patch["sections"] = [_validate_section(s) for s in patch["sections"]]
        # Renumber order
        for i, s in enumerate(patch["sections"]):
            s["order"] = i
    if "theme" in patch and patch["theme"] is not None:
        t = patch["theme"]
        if t in THEME_ALIASES:
            t = THEME_ALIASES[t]
        if t not in THEMES:
            raise HTTPException(400, f"Unknown theme: {t}")
        patch["theme"] = t
    if "background" in patch and patch["background"] is not None:
        bg = patch["background"]
        if bg.get("texture") and bg["texture"] not in TEXTURES:
            raise HTTPException(400, f"Unknown texture: {bg['texture']}")
    return patch


@router.patch("")
async def update_studio(req: StudioUpdate, user: dict = Depends(require_role("artist", "admin"))):
    """Write to draft by default; if publish=true, apply directly to live config."""
    await _get_or_create_config(user["id"])
    payload = req.model_dump(exclude_none=True)
    publish_flag = payload.pop("publish", False)
    payload = _sanitize_patch(payload)
    now = now_iso()
    if publish_flag:
        # Apply directly to live and clear any draft
        updates = dict(payload)
        updates["updated_at"] = now
        updates["published_at"] = now
        updates["draft"] = None
        await db.studio_configs.update_one({"artist_id": user["id"]}, {"$set": updates})
    else:
        # Merge into draft
        cfg = await db.studio_configs.find_one({"artist_id": user["id"]})
        current_draft = (cfg or {}).get("draft") or {}
        current_draft.update(payload)
        current_draft["updated_at"] = now
        await db.studio_configs.update_one({"artist_id": user["id"]},
            {"$set": {"draft": current_draft, "updated_at": now}})
    return await _get_or_create_config(user["id"])


@router.post("/publish")
async def publish_studio(user: dict = Depends(require_role("artist", "admin"))):
    """Merge draft into live config and clear draft."""
    cfg = await db.studio_configs.find_one({"artist_id": user["id"]})
    if not cfg or not cfg.get("draft"):
        raise HTTPException(400, "No draft to publish")
    draft = cfg["draft"]
    # Only allowed keys
    apply = {}
    for k in ("theme", "background", "lighting", "accent_color", "typography", "sections",
              "featured_artwork_ids", "commission_open", "commission_blurb", "artist_story"):
        if k in draft:
            apply[k] = draft[k]
    apply["published_at"] = now_iso()
    apply["updated_at"] = now_iso()
    apply["draft"] = None
    await db.studio_configs.update_one({"artist_id": user["id"]}, {"$set": apply})
    return await _get_or_create_config(user["id"])


@router.post("/discard-draft")
async def discard_draft(user: dict = Depends(require_role("artist", "admin"))):
    await db.studio_configs.update_one({"artist_id": user["id"]}, {"$set": {"draft": None, "updated_at": now_iso()}})
    return await _get_or_create_config(user["id"])


# ---------- Starter Templates ----------
class ApplyTemplateReq(BaseModel):
    template_id: str
    publish: bool = False  # if true, apply straight to live


@router.post("/apply-template")
async def apply_template(req: ApplyTemplateReq, user: dict = Depends(require_role("artist", "admin"))):
    if req.template_id not in TEMPLATES:
        raise HTTPException(404, "Template not found")
    template = TEMPLATES[req.template_id]
    await _get_or_create_config(user["id"])
    # Regenerate section IDs so they're unique per artist
    payload = dict(template["config"])
    payload["sections"] = [{**s, "id": new_id()} for s in payload["sections"]]
    payload = _sanitize_patch(payload)
    now = now_iso()
    if req.publish:
        updates = dict(payload)
        updates["updated_at"] = now
        updates["published_at"] = now
        updates["draft"] = None
        await db.studio_configs.update_one({"artist_id": user["id"]}, {"$set": updates})
    else:
        cfg = await db.studio_configs.find_one({"artist_id": user["id"]})
        current_draft = (cfg or {}).get("draft") or {}
        current_draft.update(payload)
        current_draft["updated_at"] = now
        current_draft["_applied_template"] = req.template_id
        await db.studio_configs.update_one({"artist_id": user["id"]},
            {"$set": {"draft": current_draft, "updated_at": now}})
    return await _get_or_create_config(user["id"])


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
    extra = await _analytics_extra(user["id"], art_ids)
    return {
        "visits": cfg.get("visits", 0),
        "total_likes": total_likes,
        "total_comments": total_comments,
        "followers": followers,
        "sales": sales,
        "revenue": round(revenue, 2),
        "artworks_count": len(art_ids),
        "top_artworks": tops[:8],
        **extra,
    }


async def _analytics_extra(artist_id: str, art_ids: list) -> dict:
    """Saves, views, most-viewed pieces, follower growth and visit series."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    total_saves = await db.saves.count_documents({"artwork_id": {"$in": art_ids}})
    total_views = await db.artwork_views.count_documents({"artist_id": artist_id})
    # Most viewed pieces (with saves + likes per piece)
    pipeline = [{"$match": {"artist_id": artist_id}}, {"$group": {"_id": "$artwork_id", "views": {"$sum": 1}}}, {"$sort": {"views": -1}}, {"$limit": 8}]
    grouped = await db.artwork_views.aggregate(pipeline).to_list(8)
    top_viewed = []
    for g in grouped:
        art = await db.artworks.find_one({"id": g["_id"]}, {"id": 1, "title": 1, "images": 1, "status": 1})
        if not art:
            continue
        top_viewed.append({
            "id": art["id"], "title": art["title"], "images": art.get("images", []), "status": art.get("status"),
            "views": g["views"],
            "saves": await db.saves.count_documents({"artwork_id": art["id"]}),
            "likes": await db.likes.count_documents({"artwork_id": art["id"]}),
        })
    # Follower growth: cumulative followers at end of each of the last 8 weeks
    follows = await db.follows.find({"followed_id": artist_id}, {"created_at": 1}).to_list(5000)
    def _parse(ts):
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            return now
    f_dates = sorted(_parse(f.get("created_at")) for f in follows)
    growth = []
    for w in range(7, -1, -1):
        end = now - timedelta(weeks=w)
        growth.append({"label": end.strftime("%b %d"), "followers": sum(1 for d in f_dates if d <= end)})
    # Visits per day, last 14 days
    since = (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
    visits = await db.studio_visits.find({"artist_id": artist_id, "created_at": {"$gte": since.isoformat()}}, {"created_at": 1}).to_list(20000)
    by_day = {}
    for v in visits:
        by_day[_parse(v["created_at"]).strftime("%Y-%m-%d")] = by_day.get(_parse(v["created_at"]).strftime("%Y-%m-%d"), 0) + 1
    visit_series = []
    for i in range(13, -1, -1):
        d = now - timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        visit_series.append({"label": d.strftime("%b %d"), "visits": by_day.get(key, 0)})
    new_followers_30d = sum(1 for d in f_dates if d >= now - timedelta(days=30))
    return {
        "total_saves": total_saves,
        "total_views": total_views,
        "top_viewed": top_viewed,
        "follower_growth": growth,
        "visit_series": visit_series,
        "new_followers_30d": new_followers_30d,
        "visits_14d": len(visits),
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


# ---------- Polish text (Claude rewrite in artist voice) ----------
class PolishReq(BaseModel):
    body: str = Field(min_length=3, max_length=4000)
    kind: str = "text_block"  # text_block | announcement | button_cta | custom
    tone: Optional[str] = None  # optional: "punchy", "warm", "clinical", etc — otherwise inferred from studio


POLISH_SYSTEM = """You are a professional copywriter helping visual artists write compelling Studio content.

You will receive:
- The current draft text (may be rough, incomplete, or too long)
- The kind of section (announcement, text_block, button_cta blurb, or custom section)
- Context about the artist (studio theme + artist story)

Rewrite the text in the artist's authentic voice. Rules:
1. Preserve the artist's meaning and any specific facts (dates, prices, names) EXACTLY.
2. Match the section kind:
   - announcement: 1-3 punchy sentences, urgency-appropriate, avoids fluff
   - text_block: 2-5 sentences, warm and personal, invites the reader in
   - button_cta blurb: 1 tight sentence + a clear reason to click
   - custom: whatever feels right for the theme
3. Match the studio vibe: graffiti = raw + confident; luxury = refined + collected; dark = cinematic + minimal; neon = electric + direct; minimal = ultra-clean; industrial = grounded.
4. Never invent facts the artist didn't provide.
5. Keep it under the original length + 20 words unless the original was less than one sentence.
6. Do NOT wrap output in quotes, markdown, or code fences. Return only the rewritten text.
"""


@router.post("/polish-text")
async def polish_text(req: PolishReq, user: dict = Depends(require_role("artist", "admin"))):
    """Rewrite a snippet in the artist's voice using Claude. Draft-safe — this endpoint
    returns text only; the frontend decides where to apply it."""
    try:
        cfg = await _get_or_create_config(user["id"])
        # Effective values: draft over published
        d = cfg.get("draft") or {}
        theme_id = d.get("theme") or cfg.get("theme") or "urban_graffiti"
        theme = THEMES.get(theme_id, THEMES["urban_graffiti"])
        story = d.get("artist_story") or cfg.get("artist_story") or {}
        story_bits = [f"{k}: {v}" for k, v in story.items() if v and k in ("location", "style", "influences", "years_active")]
        artist_context = f"Artist: {user['name']}\nStudio theme: {theme_id} ({theme['vibe']})\n" + ("\n".join(story_bits) if story_bits else "No artist story provided yet.")

        prompt = f"""SECTION KIND: {req.kind}
{'TONE: ' + req.tone if req.tone else ''}
ARTIST CONTEXT:
{artist_context}

DRAFT TEXT:
{req.body}

Rewrite the draft above."""

        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"polish-{user['id']}-{new_id()[:8]}",
            system_message=POLISH_SYSTEM,
        ).with_model("anthropic", "claude-sonnet-4-6")
        resp = await chat.send_message(UserMessage(text=prompt))
        polished = resp if isinstance(resp, str) else str(resp)
        polished = polished.strip()
        # Strip accidental code fences or wrapping quotes
        if polished.startswith("```"):
            polished = polished.split("```", 2)[1]
            if polished.startswith("text"):
                polished = polished[4:]
            polished = polished.strip()
        if (polished.startswith('"') and polished.endswith('"')) or (polished.startswith('“') and polished.endswith('”')):
            polished = polished[1:-1].strip()
        # Safety: keep length reasonable
        if len(polished) > 4200:
            polished = polished[:4200]
        return {"original": req.body, "polished": polished, "kind": req.kind}
    except Exception as e:
        raise HTTPException(500, f"Polish failed: {str(e)[:200]}")


# ---------- Studio Posts (social feed) ----------
POST_KINDS = ["update", "wip", "studio_photo", "announcement", "auction", "sold", "commission", "exhibition", "behind_scenes", "event"]


class PostCreate(BaseModel):
    kind: str = "update"
    text: str = Field(min_length=1, max_length=2000)
    image: Optional[str] = None  # storage path
    video: Optional[str] = None  # storage path (mp4/webm/mov)
    pinned: bool = False


posts_router = APIRouter(prefix="/api/posts", tags=["studio-posts"])


@posts_router.post("")
async def create_post(req: PostCreate, user: dict = Depends(require_role("artist", "admin"))):
    if req.kind not in POST_KINDS:
        raise HTTPException(400, f"Unknown kind — allowed: {', '.join(POST_KINDS)}")
    from social import _resolve_mentions, _notify_mentions
    mentions = await _resolve_mentions(req.text)
    p = {
        "id": new_id(),
        "artist_id": user["id"],
        "artist_name": user["name"],
        "kind": req.kind, "text": req.text, "image": req.image, "video": req.video,
        "pinned": req.pinned,
        "mentions": mentions,
        "like_count": 0, "comment_count": 0,
        "created_at": now_iso(),
    }
    await db.studio_posts.insert_one(p)
    from engage import notify_followers_soon
    notify_followers_soon(user["id"], "followed_new_post", f"{user['name']} posted", (p.get("text") or p.get("kind", "update"))[:120],
                          f"/artist/{user['id']}", post_id=p["id"], preview=(p.get("text") or "")[:120], post_kind=p.get("kind"))
    await _notify_mentions(mentions, user, "mentioned_in_post", post_id=p["id"])
    return strip_mongo(p)


@posts_router.get("")
async def list_posts(artist_id: str, limit: int = 30):
    cursor = db.studio_posts.find({"artist_id": artist_id, "hidden": {"$ne": True}}).sort([("pinned", -1), ("created_at", -1)]).limit(limit)
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
