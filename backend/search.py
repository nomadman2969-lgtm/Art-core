"""Search: artworks + artists."""
import re
from typing import Optional
from fastapi import APIRouter, Depends
from db import db, strip_mongo
from auth import public_user

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
async def search(q: str, limit: int = 30):
    q = q.strip()
    if not q:
        return {"artworks": [], "artists": []}
    rx = re.compile(re.escape(q), re.IGNORECASE)
    art_cursor = db.artworks.find({
        "status": {"$in": ["live", "sold"]},
        "$or": [{"title": rx}, {"description": rx}, {"medium": rx}, {"style": rx}],
    }).limit(limit)
    artworks = []
    for a in await art_cursor.to_list(limit):
        a = strip_mongo(a)
        artist = await db.users.find_one({"id": a.get("artist_id")})
        if artist:
            a["artist"] = {"id": artist["id"], "name": artist["name"]}
        artworks.append(a)

    artist_cursor = db.users.find({
        "role": "artist",
        "$or": [{"name": rx}, {"bio": rx}, {"email": rx}],
    }).limit(limit)
    artists = [public_user(strip_mongo(u)) for u in await artist_cursor.to_list(limit)]
    return {"artworks": artworks, "artists": artists}
