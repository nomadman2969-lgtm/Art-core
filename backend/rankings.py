"""Artist rankings: computed tier score across sales, followers, engagement."""
from typing import Optional
from fastapi import APIRouter, HTTPException
from db import db, strip_mongo

router = APIRouter(prefix="/api/rankings", tags=["rankings"])

TIERS = [
    {"name": "Legendary", "min": 3000, "color": "#FFD700", "order": 6},
    {"name": "Diamond", "min": 1200, "color": "#00E5FF", "order": 5},
    {"name": "Platinum", "min": 600, "color": "#E5E4E2", "order": 4},
    {"name": "Gold", "min": 250, "color": "#F5A623", "order": 3},
    {"name": "Silver", "min": 100, "color": "#C0C0C0", "order": 2},
    {"name": "Bronze", "min": 0, "color": "#CD7F32", "order": 1},
]


def tier_for(score: float) -> dict:
    for t in TIERS:
        if score >= t["min"]:
            return t
    return TIERS[-1]


async def compute_score(user_id: str) -> dict:
    sales = await db.artworks.count_documents({"artist_id": user_id, "status": "sold"})
    followers = await db.follows.count_documents({"followed_id": user_id})
    artworks = await db.artworks.count_documents({"artist_id": user_id, "status": {"$in": ["live", "sold"]}})
    # likes received on artist's works
    art_ids = [a["id"] for a in await db.artworks.find({"artist_id": user_id}, {"id": 1}).to_list(1000)]
    likes_received = await db.likes.count_documents({"artwork_id": {"$in": art_ids}}) if art_ids else 0
    commissions_done = await db.commissions.count_documents({"artist_id": user_id, "status": "approved"})
    score = sales * 50 + followers * 10 + likes_received * 2 + artworks * 5 + commissions_done * 30
    tier = tier_for(score)
    return {
        "score": score, "tier": tier["name"], "tier_color": tier["color"], "tier_order": tier["order"],
        "breakdown": {
            "sales": sales, "followers": followers, "artworks": artworks,
            "likes_received": likes_received, "commissions_done": commissions_done,
        },
    }


@router.get("/tiers")
async def list_tiers():
    return TIERS


@router.get("/leaderboard")
async def leaderboard(limit: int = 50):
    artists = await db.users.find({"role": "artist"}).to_list(1000)
    scored = []
    for u in artists:
        u = strip_mongo(u)
        s = await compute_score(u["id"])
        scored.append({
            "id": u["id"], "name": u["name"], "bio": u.get("bio"),
            **s,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


@router.get("/{user_id}")
async def user_rank(user_id: str):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "Not found")
    s = await compute_score(user_id)
    # find position in leaderboard
    lb = await leaderboard(limit=10000)
    position = next((i + 1 for i, r in enumerate(lb) if r["id"] == user_id), None)
    return {**s, "position": position, "total_artists": len(lb)}
