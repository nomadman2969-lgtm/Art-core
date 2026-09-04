"""Artwork + upload + gallery endpoints."""
import os
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Response
from pydantic import BaseModel, Field
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


@router.get("/files/{path:path}")
async def download(path: str):
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not record:
        raise HTTPException(404, "File not found")
    data, ctype = get_object(path)
    return Response(content=data, media_type=record.get("content_type", ctype))


# ---------- Artwork models ----------
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
        art["artist"] = {"id": artist["id"], "name": artist["name"], "bio": artist.get("bio")}
    return art


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
):
    q: dict = {"status": {"$in": ["live", "sold"]}}
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
    cursor = db.artworks.find(q).sort(sort_key).limit(limit)
    return [await _enrich(a) for a in await cursor.to_list(limit)]


@router.get("/artworks/aotw")
async def get_aotw():
    art = await db.artworks.find_one({"aotw": True})
    if not art:
        return None
    return await _enrich(art)


@router.get("/artworks/{artwork_id}")
async def get_artwork(artwork_id: str):
    art = await db.artworks.find_one({"id": artwork_id})
    if not art:
        raise HTTPException(404, "Not found")
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
