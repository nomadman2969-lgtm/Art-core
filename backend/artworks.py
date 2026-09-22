"""Artwork + upload + gallery endpoints."""
import os
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Response, Header
from pydantic import BaseModel, Field, field_validator
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, get_optional_user, require_role, public_user
from storage import put_object, get_object, compress_image, APP_NAME

router = APIRouter(prefix="/api", tags=["artworks"])

MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp",
}

VIDEO_MIME = {
    "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime",
    "m4v": "video/mp4",
}
MAX_VIDEO_SIZE = 60 * 1024 * 1024  # 60 MB (short vertical clips)


# ---------- Upload ----------
@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    ext = (file.filename or "img").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    if ext not in MIME:
        raise HTTPException(400, "Unsupported image type")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    data = compress_image(data)
    path = f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.jpg"
    result = put_object(path, data, "image/jpeg")
    await db.files.insert_one({
        "id": new_id(),
        "storage_path": result["path"],
        "user_id": user["id"],
        "original_filename": file.filename,
        "content_type": "image/jpeg",
        "size": result.get("size"),
        "is_deleted": False,
        "created_at": now_iso(),
    })
    return {"path": result["path"], "url": f"/api/files/{result['path']}"}


@router.post("/upload/video")
async def upload_video(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Short-form vertical clips for feed posts. Max 60MB, mp4/webm/mov."""
    ext = (file.filename or "vid").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "mp4"
    if ext not in VIDEO_MIME:
        raise HTTPException(400, "Unsupported video type — use mp4, webm, or mov")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > MAX_VIDEO_SIZE:
        raise HTTPException(400, f"Video too large — max {MAX_VIDEO_SIZE // (1024 * 1024)}MB")
    ctype = VIDEO_MIME[ext]
    # Normalize .m4v to .mp4
    save_ext = "mp4" if ext in ("mp4", "m4v") else ext
    path = f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.{save_ext}"
    result = put_object(path, data, ctype)
    await db.files.insert_one({
        "id": new_id(),
        "storage_path": result["path"],
        "user_id": user["id"],
        "original_filename": file.filename,
        "content_type": ctype,
        "size": result.get("size", len(data)),
        "kind": "video",
        "is_deleted": False,
        "created_at": now_iso(),
    })
    return {"path": result["path"], "url": f"/api/files/{result['path']}", "content_type": ctype, "size": len(data)}


THUMB_WIDTHS = (240, 480, 960)


PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "Vary": "Authorization", "Referrer-Policy": "no-referrer"}
SIGNED_TTL = 15 * 60


def sign_file_url(path: str, ttl: int = SIGNED_TTL) -> str:
    """Short-lived, path-scoped link for private assets — never carries the account JWT."""
    import hmac as _hmac, hashlib as _hl, time as _t, os as _os
    clean = (path or "").replace("/api/files/", "").lstrip("/")
    exp = int(_t.time()) + ttl
    sig = _hmac.new(_os.environ["JWT_SECRET"].encode(), f"{clean}:{exp}".encode(), _hl.sha256).hexdigest()[:40]
    return f"/api/files/{clean}?exp={exp}&sig={sig}"


def _signature_ok(path: str, exp: Optional[int], sig: Optional[str]) -> bool:
    import hmac as _hmac, hashlib as _hl, time as _t, os as _os
    if not exp or not sig or exp < int(_t.time()):
        return False
    expected = _hmac.new(_os.environ["JWT_SECRET"].encode(), f"{path}:{exp}".encode(), _hl.sha256).hexdigest()[:40]
    return _hmac.compare_digest(expected, sig)


async def _authorize_private(record: dict, authorization: Optional[str]):
    """Private assets (dispute photos, DM images): only the parties on that order/thread or an admin."""
    from auth import get_current_user
    user = await get_current_user(authorization)
    if user.get("role") == "admin":
        return
    scope = record.get("scope") or {}
    if scope.get("kind") == "thread" and user["id"] in (scope.get("users") or []):
        return
    if scope.get("kind") == "order":
        o = await db.orders.find_one({"id": scope.get("order_id")})
        if o and (o.get("buyer_id") == user["id"] or any(p.get("artist_id") == user["id"] for p in o.get("artist_payouts", []))):
            return
    if record.get("user_id") == user["id"]:
        return
    raise HTTPException(403, "Private file")


async def mark_private(paths: list, scope: dict):
    clean = [p.replace("/api/files/", "").lstrip("/") for p in paths if p and not p.startswith("http")]
    if clean:
        await db.files.update_many({"storage_path": {"$in": clean}}, {"$set": {"private": True, "scope": scope}})


@router.get("/files/{path:path}")
async def download(path: str, w: Optional[int] = None, exp: Optional[int] = None, sig: Optional[str] = None, authorization: Optional[str] = Header(None)):
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not record:
        raise HTTPException(404, "File not found")
    import hashlib as _hl
    headers = {"Cache-Control": "public, max-age=31536000, immutable",
               "CDN-Cache-Control": "public, max-age=31536000",
               "ETag": '"' + _hl.sha256(f"{path}:{w or 0}:{record.get('size', 0)}".encode()).hexdigest()[:32] + '"'}
    if record.get("private"):
        if not _signature_ok(path, exp, sig):
            await _authorize_private(record, authorization)
        headers = {**PRIVATE_HEADERS, "ETag": headers["ETag"]}
    ctype_rec = record.get("content_type", "")
    if w and ctype_rec.startswith("image/") and "svg" not in ctype_rec:
        w = min(THUMB_WIDTHS, key=lambda x: abs(x - w))
        tpath = f"thumbs/{w}/{path}"
        try:
            data, _ = get_object(tpath)
            return Response(content=data, media_type="image/jpeg", headers=headers)
        except Exception:
            pass
        data, _ = get_object(path)
        try:
            from PIL import Image, ImageOps
            import io as _io
            img = ImageOps.exif_transpose(Image.open(_io.BytesIO(data))).convert("RGB")
            if img.width > w:
                img = img.resize((w, max(1, round(img.height * w / img.width))), Image.LANCZOS)
            out = _io.BytesIO(); img.save(out, format="JPEG", quality=78, optimize=True, progressive=True)
            thumb = out.getvalue()
            try:
                put_object(tpath, thumb, "image/jpeg")
            except Exception:
                pass
            return Response(content=thumb, media_type="image/jpeg", headers=headers)
        except Exception:
            return Response(content=data, media_type=ctype_rec, headers=headers)
    data, ctype = get_object(path)
    return Response(content=data, media_type=ctype_rec or ctype, headers=headers)


# ---------- Artwork models ----------
FURNITURE_TYPES = ["chair", "table", "dresser", "cabinet", "lamp", "mirror", "shelf", "bench", "other"]


class ArtworkCreate(BaseModel):
    title: str
    description: str
    medium: str
    style: Optional[str] = None
    color: Optional[str] = None
    width_in: float
    height_in: float
    price: float = Field(gt=0)
    images: List[str] = Field(min_length=1)  # storage paths
    # Extended marketplace fields
    year: Optional[int] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    quantity: int = Field(default=1, ge=1)
    kind: str = "original"  # original | print | digital
    section: str = "art"  # art | upcycle
    furniture_type: Optional[str] = None  # chair | table | dresser | cabinet | lamp | mirror | shelf | bench | other
    before_image: Optional[str] = None  # storage path — the piece before it became art
    materials: Optional[str] = Field(default=None, max_length=200)
    # eBay-style fulfilment: seller ships their own way or offers local pickup
    delivery: List[str] = Field(default_factory=lambda: ["ships"])  # ships | local_pickup
    location: Optional[dict] = None  # {lat, lng, city}

    @field_validator("delivery")
    @classmethod
    def _delivery(cls, v):
        v = [x for x in v if x in ("ships", "local_pickup")]
        return v or ["ships"]

    @field_validator("section")
    @classmethod
    def _section(cls, v):
        if v not in ("art", "upcycle"):
            raise ValueError("section must be art or upcycle")
        return v

    @field_validator("furniture_type")
    @classmethod
    def _furn(cls, v):
        if v is not None and v not in FURNITURE_TYPES:
            raise ValueError(f"furniture_type must be one of {FURNITURE_TYPES}")
        return v
    shipping_info: Optional[str] = None
    coa: Optional[str] = None  # Certificate of authenticity notes


class ArtworkUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    medium: Optional[str] = None
    style: Optional[str] = None
    color: Optional[str] = None
    width_in: Optional[float] = None
    height_in: Optional[float] = None
    price: Optional[float] = None
    images: Optional[List[str]] = None
    year: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    quantity: Optional[int] = None
    kind: Optional[str] = None
    shipping_info: Optional[str] = None
    coa: Optional[str] = None


async def _enrich(art: dict) -> dict:
    art = strip_mongo(art)
    if not art:
        return art
    artist = await db.users.find_one({"id": art.get("artist_id")})
    if artist:
        from auth import _pro_active
        art["artist"] = {"id": artist["id"], "name": artist["name"], "bio": artist.get("bio"),
                         "founding_member": bool(artist.get("founding_member")), "pro_active": _pro_active(artist)}
    return art


FURNITURE_LABELS = {"chair": "Chairs", "table": "Tables", "dresser": "Dressers", "cabinet": "Cabinets", "lamp": "Lamps", "mirror": "Mirrors", "shelf": "Shelves", "bench": "Benches", "other": "Other"}


@router.get("/upcycle/meta")
async def upcycle_meta():
    counts = {}
    async for row in db.artworks.aggregate([{"$match": {"section": "upcycle", "status": {"$in": ["live", "sold"]}}}, {"$group": {"_id": "$furniture_type", "n": {"$sum": 1}}}]):
        counts[row["_id"] or "other"] = row["n"]
    return {"types": [{"key": k, "label": FURNITURE_LABELS[k], "count": counts.get(k, 0)} for k in FURNITURE_TYPES], "total": sum(counts.values())}


# ---------- Artist endpoints ----------
@router.post("/artworks")
async def create_artwork(req: ArtworkCreate, user: dict = Depends(require_role("artist", "admin"))):
    art = {
        "id": new_id(),
        "artist_id": user["id"],
        **req.model_dump(),
        "status": "pending_fee",  # pending_fee -> live -> sold
        "featured": False,
        "aotw": False,
        "aotw_submitted": False,
        "created_at": now_iso(),
    }
    await db.artworks.insert_one(art)
    return await _enrich(art)


@router.get("/artworks/mine")
async def my_artworks(user: dict = Depends(require_role("artist", "admin"))):
    cursor = db.artworks.find({"artist_id": user["id"]}).sort("created_at", -1)
    return [await _enrich(a) for a in await cursor.to_list(500)]


@router.patch("/artworks/{artwork_id}")
async def update_artwork(artwork_id: str, req: ArtworkUpdate, user: dict = Depends(get_current_user)):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    if user["role"] != "admin" and art["artist_id"] != user["id"]:
        raise HTTPException(403, "Not yours")
    updates = {k: v for k, v in req.model_dump(exclude_none=True).items()}
    if updates:
        await db.artworks.update_one({"id": artwork_id}, {"$set": updates})
    return await _enrich(await db.artworks.find_one({"id": artwork_id}))


@router.delete("/artworks/{artwork_id}")
async def delete_artwork(artwork_id: str, user: dict = Depends(get_current_user)):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    if user["role"] != "admin" and art["artist_id"] != user["id"]:
        raise HTTPException(403, "Not yours")
    if art.get("status") == "sold":
        raise HTTPException(400, "Cannot delete sold artwork")
    await db.artworks.delete_one({"id": artwork_id})
    return {"deleted": 1}


@router.post("/artworks/{artwork_id}/mark-sold")
async def mark_sold(artwork_id: str, user: dict = Depends(get_current_user)):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    if user["role"] != "admin" and art["artist_id"] != user["id"]:
        raise HTTPException(403, "Not yours")
    await db.artworks.update_one({"id": artwork_id}, {"$set": {"status": "sold", "sold_offline": True}})
    return {"ok": True}


@router.post("/artworks/{artwork_id}/submit-aotw")
async def submit_aotw(artwork_id: str, user: dict = Depends(require_role("artist", "admin"))):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art or (art["artist_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "Not found")
    if art["status"] != "live":
        raise HTTPException(400, "Only live artworks can be submitted")
    await db.artworks.update_one({"id": artwork_id}, {"$set": {"aotw_submitted": True}})
    return {"ok": True}


# ---------- Public browse ----------
@router.get("/artworks")
async def list_artworks(
    medium: Optional[str] = None,
    style: Optional[str] = None,
    color: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    artist_id: Optional[str] = None,
    featured: Optional[bool] = None,
    sort: str = "recent",
    limit: int = 60,
    section: Optional[str] = None,
    furniture_type: Optional[str] = None,
    near_lat: Optional[float] = None,
    near_lng: Optional[float] = None,
    radius_km: float = 50,
    pickup_only: bool = False,
):
    q: dict = {"status": {"$in": ["live", "sold"]}}
    if section == "upcycle":
        q["section"] = "upcycle"
    elif section == "art":
        q["section"] = {"$ne": "upcycle"}
    if furniture_type: q["furniture_type"] = furniture_type
    if pickup_only: q["delivery"] = "local_pickup"
    if near_lat is not None and near_lng is not None: q["location.lat"] = {"$exists": True}
    if medium: q["medium"] = medium
    if style: q["style"] = style
    if color: q["color"] = color
    if artist_id: q["artist_id"] = artist_id
    if featured is not None: q["featured"] = featured
    if min_price is not None or max_price is not None:
        pr = {}
        if min_price is not None: pr["$gte"] = min_price
        if max_price is not None: pr["$lte"] = max_price
        q["price"] = pr
    sort_key = [("price", 1)] if sort == "price_asc" else \
               [("price", -1)] if sort == "price_desc" else \
               [("created_at", -1)]
    cursor = db.artworks.find(q).sort(sort_key).limit(limit if near_lat is None else 400)
    out = [await _enrich(a) for a in await cursor.to_list(limit if near_lat is None else 400)]
    if sort not in ("price_asc", "price_desc"):
        out.sort(key=lambda a: 0 if (a.get("artist") or {}).get("pro_active") else 1)  # Pro boost, stable
    if near_lat is not None and near_lng is not None:
        from math import radians, sin, cos, asin, sqrt
        def dist_km(a, b):
            la1, lo1, la2, lo2 = map(radians, [a[0], a[1], b[0], b[1]])
            h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
            return 2 * 6371 * asin(sqrt(h))
        for a in out:
            loc = a.get("location") or {}
            a["distance_km"] = round(dist_km((near_lat, near_lng), (loc.get("lat"), loc.get("lng"))), 1) if loc.get("lat") is not None else None
        out = sorted([a for a in out if a["distance_km"] is not None and a["distance_km"] <= radius_km], key=lambda a: a["distance_km"])[:limit]
    return out


@router.get("/artworks/aotw")
async def get_aotw():
    art = await db.artworks.find_one({"aotw": True})
    if not art:
        return None
    return await _enrich(art)


@router.get("/artworks/{artwork_id}")
async def get_artwork(artwork_id: str, viewer: Optional[dict] = Depends(get_optional_user)):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
    if not viewer or viewer["id"] != art.get("artist_id"):
        await db.artwork_views.insert_one({"id": new_id(), "artwork_id": artwork_id, "artist_id": art.get("artist_id"), "viewer_id": viewer["id"] if viewer else None, "created_at": now_iso()})
        await db.artworks.update_one({"id": artwork_id}, {"$inc": {"views": 1}})
    return await _enrich(art)


# ---------- Artist portfolio ----------
@router.get("/artists")
async def list_artists():
    cursor = db.users.find({"role": "artist"}).sort("created_at", -1)
    out = []
    for u in await cursor.to_list(500):
        u = strip_mongo(u)
        art_count = await db.artworks.count_documents({"artist_id": u["id"], "status": {"$in": ["live", "sold"]}})
        out.append({**public_user(u), "artwork_count": art_count})
    return out


@router.get("/artists/{artist_id}")
async def get_artist(artist_id: str):
    u = await db.users.find_one({"id": artist_id, "role": "artist"})
    if not u:
        raise HTTPException(404, "Not found")
    artworks = await db.artworks.find({"artist_id": artist_id, "status": {"$in": ["live", "sold"]}}).sort("created_at", -1).to_list(200)
    return {
        **public_user(strip_mongo(u)),
        "artworks": [await _enrich(a) for a in artworks],
    }
