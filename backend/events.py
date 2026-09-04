"""Art events — physical + virtual events with geolocation and RSVP."""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, get_optional_user, require_role

router = APIRouter(prefix="/api/events", tags=["events"])

EVENT_CATEGORIES = [
    "gallery_opening", "pop_up", "festival", "meetup",
    "workshop", "live_painting", "virtual", "market",
]


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=300)
    city: Optional[str] = Field(default=None, max_length=100)


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=3, max_length=4000)
    category: str = "gallery_opening"
    location: Location
    start_at: str  # ISO
    end_at: Optional[str] = None
    cover_image: Optional[str] = None  # storage path
    max_capacity: Optional[int] = Field(default=None, ge=1, le=100000)
    is_free: bool = True
    ticket_price: Optional[float] = Field(default=None, ge=0)

    @field_validator("category")
    @classmethod
    def _check_cat(cls, v):
        if v not in EVENT_CATEGORIES:
            raise ValueError(f"Category must be one of {EVENT_CATEGORIES}")
        return v

    @field_validator("start_at", "end_at")
    @classmethod
    def _check_iso(cls, v):
        if v is None:
            return v
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception as e:  # noqa
            raise ValueError("must be ISO datetime")
        return v


async def _enrich(e: dict, me: Optional[dict] = None) -> dict:
    e = strip_mongo(e)
    if not e:
        return e
    host = await db.users.find_one({"id": e.get("host_id")})
    if host:
        e["host"] = {"id": host["id"], "name": host["name"], "role": host.get("role")}
    e["rsvp_count"] = await db.event_rsvps.count_documents({"event_id": e["id"]})
    if me:
        e["rsvped"] = bool(await db.event_rsvps.find_one({"event_id": e["id"], "user_id": me["id"]}))
    return e


@router.post("")
async def create_event(req: EventCreate, user: dict = Depends(require_role("artist", "admin"))):
    if not req.is_free and (req.ticket_price is None or req.ticket_price <= 0):
        raise HTTPException(400, "Paid events need a ticket_price > 0")
    e = {
        "id": new_id(),
        "host_id": user["id"],
        "host_name": user["name"],
        "title": req.title,
        "description": req.description,
        "category": req.category,
        "location": req.location.model_dump(),
        "start_at": req.start_at,
        "end_at": req.end_at,
        "cover_image": req.cover_image,
        "max_capacity": req.max_capacity,
        "is_free": req.is_free,
        "ticket_price": req.ticket_price if not req.is_free else None,
        "cancelled": False,
        "created_at": now_iso(),
    }
    await db.events.insert_one(e)
    return await _enrich(e, user)


@router.get("")
async def list_events(
    upcoming_only: bool = True,
    category: Optional[str] = None,
    host_id: Optional[str] = None,
    near_lat: Optional[float] = None,
    near_lng: Optional[float] = None,
    radius_km: float = 50,
    limit: int = 60,
    me: Optional[dict] = Depends(get_optional_user),
):
    limit = max(1, min(limit, 200))
    q: dict = {"cancelled": {"$ne": True}}
    if category:
        if category not in EVENT_CATEGORIES:
            raise HTTPException(400, "Unknown category")
        q["category"] = category
    if host_id:
        q["host_id"] = host_id
    if upcoming_only:
        q["start_at"] = {"$gte": now_iso()}
    cursor = db.events.find(q).sort("start_at", 1).limit(limit)
    events = [await _enrich(e, me) for e in await cursor.to_list(limit)]
    # Naive haversine filter if requested
    if near_lat is not None and near_lng is not None:
        import math

        def dist_km(a, b):
            R = 6371.0
            dlat = math.radians(b[0] - a[0])
            dlng = math.radians(b[1] - a[1])
            aa = (math.sin(dlat / 2) ** 2 +
                  math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) *
                  math.sin(dlng / 2) ** 2)
            return 2 * R * math.asin(math.sqrt(aa))
        origin = (near_lat, near_lng)
        events = [e for e in events if dist_km(origin, (e["location"]["lat"], e["location"]["lng"])) <= radius_km]
    return events


@router.get("/{event_id}")
async def get_event(event_id: str, me: Optional[dict] = Depends(get_optional_user)):
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    return await _enrich(e, me)


@router.delete("/{event_id}")
async def cancel_event(event_id: str, user: dict = Depends(get_current_user)):
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    if e["host_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not yours")
    await db.events.update_one({"id": event_id}, {"$set": {"cancelled": True}})
    # Notify all RSVP'd users
    rsvps = await db.event_rsvps.find({"event_id": event_id}).to_list(2000)
    for r in rsvps:
        if r["user_id"] == user["id"]:
            continue
        await db.notifications.insert_one({
            "id": new_id(), "user_id": r["user_id"], "kind": "event_cancelled",
            "event_id": event_id, "event_title": e["title"],
            "read": False, "created_at": now_iso(),
        })
    return {"cancelled": True}


@router.post("/{event_id}/rsvp")
async def rsvp(event_id: str, user: dict = Depends(get_current_user)):
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    if e.get("cancelled"):
        raise HTTPException(400, "Event was cancelled")
    existing = await db.event_rsvps.find_one({"event_id": event_id, "user_id": user["id"]})
    if existing:
        await db.event_rsvps.delete_one({"_id": existing["_id"]})
        return {"rsvped": False, "count": await db.event_rsvps.count_documents({"event_id": event_id})}
    # Capacity check
    if e.get("max_capacity"):
        count = await db.event_rsvps.count_documents({"event_id": event_id})
        if count >= e["max_capacity"]:
            raise HTTPException(400, "Event is full")
    await db.event_rsvps.insert_one({
        "id": new_id(), "event_id": event_id, "user_id": user["id"],
        "user_name": user["name"], "created_at": now_iso(),
    })
    # Notify host once per user
    if e["host_id"] != user["id"]:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": e["host_id"], "kind": "event_rsvp",
            "event_id": event_id, "event_title": e["title"],
            "from_user_id": user["id"], "from_user_name": user["name"],
            "read": False, "created_at": now_iso(),
        })
    return {"rsvped": True, "count": await db.event_rsvps.count_documents({"event_id": event_id})}


@router.get("/{event_id}/attendees")
async def attendees(event_id: str, limit: int = 100):
    cursor = db.event_rsvps.find({"event_id": event_id}).sort("created_at", 1).limit(limit)
    return [strip_mongo(r) for r in await cursor.to_list(limit)]
