"""Campus Pages — artists tag their school; /campus/{slug} auto-aggregates their studios, work and events."""
import re
import unicodedata
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, require_role, _pro_active
from campus_seed import SCHOOLS, ALIASES

router = APIRouter(prefix="/api/campus", tags=["campus"])
admin_router = APIRouter(prefix="/api/admin/campuses", tags=["admin-campus"])


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:80] or "school"


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower())


def _public(c: dict) -> dict:
    return {"id": c["id"], "slug": c["slug"], "name": c["name"], "city": c.get("city"), "country": c.get("country"),
            "status": c.get("status", "approved"), "featured": bool(c.get("featured"))}


async def ensure_seed():
    await db.campuses.create_index("slug", unique=True)
    await db.campuses.create_index("norm")
    if await db.campuses.count_documents({"seeded": True}) >= len(SCHOOLS) and await db.campuses.count_documents({"aliases": {"$exists": True}}) >= len(ALIASES):
        return
    existing = {c["slug"] for c in await db.campuses.find({}, {"slug": 1}).to_list(5000)}
    docs = []
    for name, city, country in SCHOOLS:
        slug = slugify(name)
        if slug in existing:
            continue
        existing.add(slug)
        docs.append({"id": new_id(), "slug": slug, "name": name, "norm": _norm(name), "city": city, "country": country,
                     "status": "approved", "seeded": True, "featured": False, "created_at": now_iso()})
    if docs:
        await db.campuses.insert_many(docs)
    for name, al in ALIASES.items():
        await db.campuses.update_one({"slug": slugify(name)}, {"$set": {"aliases": al}})


async def _resolve(slug_or_id: str) -> Optional[dict]:
    c = await db.campuses.find_one({"$or": [{"slug": slug_or_id}, {"id": slug_or_id}]})
    hops = 0
    while c and c.get("merged_into") and hops < 5:
        c = await db.campuses.find_one({"id": c["merged_into"]})
        hops += 1
    return c


async def _set_user_campus(user_id: str, c: Optional[dict]):
    if c:
        await db.users.update_one({"id": user_id}, {"$set": {"campus_id": c["id"], "campus_slug": c["slug"], "campus_name": c["name"]}})
    else:
        await db.users.update_one({"id": user_id}, {"$unset": {"campus_id": "", "campus_slug": "", "campus_name": ""}})


async def _sync_denorm(c: dict):
    patch = {"campus_slug": c["slug"], "campus_name": c["name"]}
    await db.users.update_many({"campus_id": c["id"]}, {"$set": patch})
    await db.events.update_many({"campus_id": c["id"]}, {"$set": patch})


# ---------- public ----------
@router.get("/search")
async def search(q: str = "", limit: int = 12):
    q = q.strip()
    if len(q) < 2:
        return []
    rx = {"$regex": re.escape(q), "$options": "i"}
    cur = db.campuses.find({"status": {"$in": ["approved", "pending"]}, "merged_into": None,
                            "$or": [{"name": rx}, {"city": rx}, {"aliases": rx}]}).limit(max(1, min(limit, 25)))
    ql = q.lower()
    rows = await cur.to_list(25)
    rows.sort(key=lambda c: (not (c["name"].lower().startswith(ql) or any(a.lower().startswith(ql) for a in c.get("aliases") or [])), c["name"]))
    return [{**_public(c), "aliases": c.get("aliases") or []} for c in rows]


@router.get("")
async def directory(limit: int = 60):
    pipeline = [{"$match": {"role": "artist", "campus_id": {"$ne": None}}}, {"$group": {"_id": "$campus_id", "n": {"$sum": 1}}}]
    counts = {r["_id"]: r["n"] async for r in db.users.aggregate(pipeline)}
    ids = list(counts.keys())
    feat = await db.campuses.find({"featured": True, "merged_into": None, "status": "approved"}, {"id": 1}).to_list(50)
    ids = list({*ids, *[f["id"] for f in feat]})
    cs = await db.campuses.find({"id": {"$in": ids}, "merged_into": None, "status": {"$in": ["approved", "pending"]}}).to_list(500)
    out = [{**_public(c), "artist_count": counts.get(c["id"], 0)} for c in cs]
    out.sort(key=lambda c: (-int(c["featured"]), -c["artist_count"], c["name"]))
    return out[:max(1, min(limit, 200))]


class SetSchoolReq(BaseModel):
    campus_id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=3, max_length=140)
    city: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=60)


@router.get("/me")
async def my_school(user: dict = Depends(get_current_user)):
    if not user.get("campus_id"):
        return None
    c = await _resolve(user["campus_id"])
    return _public(c) if c else None


@router.post("/me")
async def set_my_school(req: SetSchoolReq, user: dict = Depends(require_role("artist", "admin"))):
    if req.campus_id:
        c = await _resolve(req.campus_id)
        if not c or c.get("status") == "rejected":
            raise HTTPException(404, "School not found")
    elif req.name:
        c = await db.campuses.find_one({"norm": _norm(req.name), "merged_into": None})
        if c and c.get("status") == "rejected":
            raise HTTPException(400, "That school was declined by moderators")
        if not c:
            slug = slugify(req.name)
            if await db.campuses.find_one({"slug": slug}):
                slug = f"{slug}-{new_id()[:4]}"
            c = {"id": new_id(), "slug": slug, "name": req.name.strip(), "norm": _norm(req.name), "city": (req.city or "").strip() or None,
                 "country": (req.country or "").strip() or None, "status": "pending", "seeded": False, "featured": False,
                 "created_by": user["id"], "created_at": now_iso()}
            await db.campuses.insert_one(c)
            for a in await db.users.find({"role": "admin"}, {"id": 1}).to_list(20):
                await db.notifications.insert_one({"id": new_id(), "user_id": a["id"], "kind": "campus_pending", "campus_id": c["id"],
                                                   "campus_name": c["name"], "from_user_id": user["id"], "from_user_name": user["name"],
                                                   "read": False, "created_at": now_iso()})
    else:
        raise HTTPException(400, "Pick a school or type its name")
    await _set_user_campus(user["id"], c)
    return _public(c)


@router.delete("/me")
async def clear_my_school(user: dict = Depends(get_current_user)):
    await _set_user_campus(user["id"], None)
    return {"ok": True}


@router.get("/{slug}")
async def campus_page(slug: str):
    c = await _resolve(slug)
    if not c or c.get("status") == "rejected":
        raise HTTPException(404, "Campus not found")
    artists_raw = await db.users.find({"campus_id": c["id"], "role": "artist"}).to_list(500)
    ids = [a["id"] for a in artists_raw]
    sold_by = {r["_id"]: r["n"] async for r in db.orders.aggregate([
        {"$match": {"artist_payouts.artist_id": {"$in": ids}, "refunded": {"$ne": True}}}, {"$unwind": "$artist_payouts"},
        {"$match": {"artist_payouts.artist_id": {"$in": ids}}}, {"$group": {"_id": "$artist_payouts.artist_id", "n": {"$sum": 1}}}])} if ids else {}
    followers_by = {r["_id"]: r["n"] async for r in db.follows.aggregate([{"$match": {"followed_id": {"$in": ids}}}, {"$group": {"_id": "$followed_id", "n": {"$sum": 1}}}])} if ids else {}
    works_by = {r["_id"]: r["n"] async for r in db.artworks.aggregate([{"$match": {"artist_id": {"$in": ids}, "status": {"$in": ["live", "sold"]}}}, {"$group": {"_id": "$artist_id", "n": {"$sum": 1}}}])} if ids else {}
    artists = [{"id": a["id"], "name": a["name"], "avatar": a.get("avatar"), "bio": a.get("bio"), "founding_member": bool(a.get("founding_member")),
                "pro_active": _pro_active(a), "sales": sold_by.get(a["id"], 0), "followers": followers_by.get(a["id"], 0), "works": works_by.get(a["id"], 0)}
               for a in artists_raw]
    artists.sort(key=lambda a: (-a["sales"], -a["followers"], a["name"]))
    arts = await db.artworks.find({"artist_id": {"$in": ids}, "status": "live"}).sort("created_at", -1).limit(24).to_list(24) if ids else []
    by_id = {a["id"]: a for a in artists}
    artworks = []
    for a in arts:
        a = strip_mongo(a)
        ar = by_id.get(a["artist_id"])
        a["artist"] = {"id": ar["id"], "name": ar["name"], "founding_member": ar["founding_member"], "pro_active": ar["pro_active"]} if ar else None
        artworks.append(a)
    from events import _enrich as _enrich_event
    ev_q = {"cancelled": {"$ne": True}, "start_at": {"$gte": now_iso()}, "$or": [{"campus_id": c["id"]}, {"host_id": {"$in": ids}}]}
    events = [await _enrich_event(e) for e in await db.events.find(ev_q).sort("start_at", 1).limit(12).to_list(12)]
    return {
        "campus": _public(c),
        "stats": {"artists": len(artists), "artworks_live": await db.artworks.count_documents({"artist_id": {"$in": ids}, "status": "live"}) if ids else 0,
                  "sales": sum(sold_by.values()), "events_upcoming": len(events)},
        "artists": artists,
        "artworks": artworks,
        "events": events,
        "leaderboard": {"sales": [a for a in artists if a["sales"] > 0][:5], "followers": sorted([a for a in artists if a["followers"] > 0], key=lambda a: -a["followers"])[:5]},
    }


# ---------- admin ----------
@admin_router.get("")
async def admin_list(status: Optional[str] = None, q: str = "", admin: dict = Depends(require_role("admin"))):
    query: dict = {"merged_into": None}
    if status:
        query["status"] = status
    if q.strip():
        query["name"] = {"$regex": re.escape(q.strip()), "$options": "i"}
    cs = await db.campuses.find(query).sort([("status", -1), ("created_at", -1)]).limit(300).to_list(300)
    counts = {r["_id"]: r["n"] async for r in db.users.aggregate([{"$match": {"campus_id": {"$in": [c["id"] for c in cs]}}}, {"$group": {"_id": "$campus_id", "n": {"$sum": 1}}}])}
    out = []
    for c in cs:
        creator = await db.users.find_one({"id": c["created_by"]}, {"name": 1, "email": 1}) if c.get("created_by") else None
        out.append({**_public(c), "artist_count": counts.get(c["id"], 0), "seeded": bool(c.get("seeded")), "created_at": c.get("created_at"),
                    "created_by": {"id": c["created_by"], "name": creator.get("name"), "email": creator.get("email")} if creator else None})
    out.sort(key=lambda c: (c["status"] != "pending", -c["artist_count"], c["name"]))
    return out


class CampusPatch(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(approved|pending|rejected)$")
    featured: Optional[bool] = None
    name: Optional[str] = Field(default=None, min_length=3, max_length=140)
    city: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=60)


@admin_router.patch("/{campus_id}")
async def admin_patch(campus_id: str, req: CampusPatch, admin: dict = Depends(require_role("admin"))):
    c = await db.campuses.find_one({"id": campus_id})
    if not c:
        raise HTTPException(404, "Not found")
    patch = req.model_dump(exclude_unset=True)
    if "name" in patch and patch["name"]:
        patch["norm"] = _norm(patch["name"])
    await db.campuses.update_one({"id": campus_id}, {"$set": patch})
    c = await db.campuses.find_one({"id": campus_id})
    if "name" in patch:
        await _sync_denorm(c)
    if patch.get("status") == "approved" and c.get("created_by") and c.get("status") != "approved_notified":
        await db.notifications.insert_one({"id": new_id(), "user_id": c["created_by"], "kind": "campus_approved", "campus_id": c["id"],
                                           "campus_name": c["name"], "campus_slug": c["slug"], "read": False, "created_at": now_iso()})
    if patch.get("status") == "rejected":
        await db.users.update_many({"campus_id": campus_id}, {"$unset": {"campus_id": "", "campus_slug": "", "campus_name": ""}})
    return _public(c)


class MergeReq(BaseModel):
    into_id: str


@admin_router.post("/{campus_id}/merge")
async def admin_merge(campus_id: str, req: MergeReq, admin: dict = Depends(require_role("admin"))):
    if campus_id == req.into_id:
        raise HTTPException(400, "Pick a different target")
    src = await db.campuses.find_one({"id": campus_id})
    dst = await _resolve(req.into_id)
    if not src or not dst or dst["id"] == src["id"]:
        raise HTTPException(404, "Campus not found")
    moved = (await db.users.update_many({"campus_id": src["id"]}, {"$set": {"campus_id": dst["id"], "campus_slug": dst["slug"], "campus_name": dst["name"]}})).modified_count
    await db.events.update_many({"campus_id": src["id"]}, {"$set": {"campus_id": dst["id"], "campus_slug": dst["slug"], "campus_name": dst["name"]}})
    await db.campuses.update_one({"id": src["id"]}, {"$set": {"merged_into": dst["id"], "status": "merged", "merged_at": now_iso()}})
    return {"ok": True, "moved_artists": moved, "into": _public(dst)}
