"""Admin endpoints: settings, AOTW curation, orders, mentorship, featured artworks."""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from db import db, new_id, now_iso, strip_mongo
from auth import require_role, public_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- settings ---
class SettingsUpdate(BaseModel):
    commission_percent: Optional[float] = None
    upload_fee: Optional[float] = None
    currency: Optional[str] = None


async def _get_settings():
    s = await db.settings.find_one({"id": "global"})
    if not s:
        default = {"id": "global", "commission_percent": 15.0, "upload_fee": 5.0, "currency": "usd", "aotw_artwork_id": None, "created_at": now_iso()}
        await db.settings.insert_one(default)
        return default
    return strip_mongo(s)


@router.get("/settings")
async def get_settings(user=Depends(require_role("admin"))):
    return await _get_settings()


@router.patch("/settings")
async def update_settings(req: SettingsUpdate, user=Depends(require_role("admin"))):
    updates = {k: v for k, v in req.model_dump(exclude_none=True).items()}
    if updates:
        await db.settings.update_one({"id": "global"}, {"$set": updates}, upsert=True)
    return await _get_settings()


# --- Featured artworks ---
class FeaturedReq(BaseModel):
    artwork_id: str
    featured: bool


@router.post("/featured")
async def set_featured(req: FeaturedReq, user=Depends(require_role("admin"))):
    art = await db.artworks.find_one({"id": req.artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    await db.artworks.update_one({"id": req.artwork_id}, {"$set": {"featured": req.featured}})
    return {"ok": True}


# --- Art of the Week ---
class AOTWReq(BaseModel):
    artwork_id: str


@router.post("/aotw")
async def set_aotw(req: AOTWReq, user=Depends(require_role("admin"))):
    art = await db.artworks.find_one({"id": req.artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    await db.artworks.update_many({"aotw": True}, {"$set": {"aotw": False}})
    await db.artworks.update_one({"id": req.artwork_id}, {"$set": {"aotw": True, "aotw_selected_at": now_iso()}})
    await db.settings.update_one({"id": "global"}, {"$set": {"aotw_artwork_id": req.artwork_id}}, upsert=True)
    return {"ok": True}


@router.get("/aotw/submissions")
async def aotw_submissions(user=Depends(require_role("admin"))):
    cursor = db.artworks.find({"aotw_submitted": True, "status": "live"}).sort("created_at", -1)
    out = []
    for a in await cursor.to_list(200):
        a = strip_mongo(a)
        artist = await db.users.find_one({"id": a["artist_id"]})
        if artist:
            a["artist"] = {"id": artist["id"], "name": artist["name"]}
        out.append(a)
    return out


# --- Orders ---
@router.get("/orders")
async def all_orders(user=Depends(require_role("admin"))):
    cursor = db.orders.find({}).sort("created_at", -1)
    orders = [strip_mongo(o) for o in await cursor.to_list(500)]
    return orders


@router.get("/artists")
async def all_artists(user=Depends(require_role("admin"))):
    cursor = db.users.find({"role": "artist"}).sort("created_at", -1)
    out = []
    for u in await cursor.to_list(500):
        u = strip_mongo(u)
        out.append(public_user(u))
    return out


# --- Mentorship ---
class MentorshipFlag(BaseModel):
    artist_id: str
    note: str


@router.post("/mentorship")
async def flag_mentorship(req: MentorshipFlag, user=Depends(require_role("admin"))):
    entry = {
        "id": new_id(),
        "artist_id": req.artist_id,
        "note": req.note,
        "resolved": False,
        "created_at": now_iso(),
    }
    await db.mentorship.insert_one(entry)
    return strip_mongo(entry)


@router.get("/mentorship")
async def list_mentorship(user=Depends(require_role("admin"))):
    cursor = db.mentorship.find({}).sort("created_at", -1)
    out = []
    for m in await cursor.to_list(500):
        m = strip_mongo(m)
        artist = await db.users.find_one({"id": m["artist_id"]})
        if artist:
            m["artist"] = {"id": artist["id"], "name": artist["name"], "email": artist["email"]}
        out.append(m)
    return out


@router.patch("/mentorship/{item_id}/resolve")
async def resolve_mentorship(item_id: str, user=Depends(require_role("admin"))):
    await db.mentorship.update_one({"id": item_id}, {"$set": {"resolved": True}})
    return {"ok": True}


# --- Dashboard stats ---
@router.get("/stats")
async def stats(user=Depends(require_role("admin"))):
    total_orders = await db.orders.count_documents({})
    orders = await db.orders.find({}).to_list(2000)
    revenue = sum(o.get("total", 0) for o in orders)
    platform_take = sum(o.get("platform_take", 0) for o in orders)
    artists = await db.users.count_documents({"role": "artist"})
    buyers = await db.users.count_documents({"role": "buyer"})
    artworks_live = await db.artworks.count_documents({"status": "live"})
    return {
        "total_orders": total_orders,
        "revenue": round(revenue, 2),
        "platform_take": round(platform_take, 2),
        "artists": artists,
        "buyers": buyers,
        "artworks_live": artworks_live,
    }


# --- Newsletter ---
class NewsletterReq(BaseModel):
    email: str


newsletter_router = APIRouter(prefix="/api", tags=["newsletter"])


@newsletter_router.post("/newsletter")
async def newsletter_signup(req: NewsletterReq):
    existing = await db.newsletter.find_one({"email": req.email.lower()})
    if existing:
        return {"ok": True, "already": True}
    await db.newsletter.insert_one({"id": new_id(), "email": req.email.lower(), "created_at": now_iso()})
    return {"ok": True}


@router.get("/newsletter")
async def list_newsletter(user=Depends(require_role("admin"))):
    cursor = db.newsletter.find({}).sort("created_at", -1)
    return [strip_mongo(n) for n in await cursor.to_list(1000)]
