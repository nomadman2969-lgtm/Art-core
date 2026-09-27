"""Art events — physical + virtual events with geolocation and RSVP."""
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, field_validator
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, get_optional_user, require_role

router = APIRouter(prefix="/api/events", tags=["events"])
log = logging.getLogger(__name__)

# key, label, color — the frontend reads this via GET /events/meta/categories
CATEGORY_META = [
    ("exhibition", "Exhibition", "#F4F4F5"),
    ("gallery_opening", "Gallery Opening", "#D4AF37"),
    ("festival", "Art Festival", "#FF6EC7"),
    ("street_art", "Street Art", "#CCFF00"),
    ("pop_up", "Pop-up", "#FF4D4D"),
    ("art_class", "Art Class", "#00E5FF"),
    ("workshop", "Workshop", "#00B8CC"),
    ("auction", "Auction", "#7C3AED"),
    ("meetup", "Meetup", "#A78BFA"),
    ("live_painting", "Live Painting", "#F5A623"),
    ("museum", "Museum", "#E4E4E7"),
    ("market", "Art Market", "#34D399"),
    ("virtual", "Virtual", "#CCFF00"),
]
EVENT_CATEGORIES = [k for k, _l, _c in CATEGORY_META]

RECURRENCE_FREQ = ["weekly", "biweekly", "monthly"]
RECURRENCE_MAX = 26  # cap: 6 months weekly, 12 months biweekly, 2 years monthly


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=300)
    city: Optional[str] = Field(default=None, max_length=100)


class Recurrence(BaseModel):
    frequency: str  # weekly | biweekly | monthly
    count: int = Field(ge=2, le=RECURRENCE_MAX)

    @field_validator("frequency")
    @classmethod
    def _check_freq(cls, v):
        if v not in RECURRENCE_FREQ:
            raise ValueError(f"Frequency must be one of {RECURRENCE_FREQ}")
        return v


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=3, max_length=4000)
    category: str = "gallery_opening"
    location: Location
    start_at: str  # ISO
    end_at: Optional[str] = None
    cover_image: Optional[str] = None  # storage path
    images: List[str] = Field(default_factory=list)
    venue: Optional[str] = Field(default=None, max_length=200)
    organizer: Optional[str] = Field(default=None, max_length=200)
    website: Optional[str] = Field(default=None, max_length=500)
    ticket_info: Optional[str] = Field(default=None, max_length=500)
    ticket_url: Optional[str] = Field(default=None, max_length=500)
    tags: List[str] = Field(default_factory=list)
    max_capacity: Optional[int] = Field(default=None, ge=1, le=100000)
    is_free: bool = True
    ticket_price: Optional[float] = Field(default=None, ge=0)
    recurrence: Optional[Recurrence] = None
    reminders_enabled: bool = True
    campus_id: Optional[str] = None

    @field_validator("website", "ticket_url")
    @classmethod
    def _url(cls, v):
        if v and not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v

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
    e["saved_count"] = await db.event_saves.count_documents({"event_id": e["id"]})
    e.setdefault("images", [])
    e.setdefault("organizer", (host or {}).get("name"))
    if me:
        e["rsvped"] = bool(await db.event_rsvps.find_one({"event_id": e["id"], "user_id": me["id"]}))
        e["saved"] = bool(await db.event_saves.find_one({"event_id": e["id"], "user_id": me["id"]}))
    return e


@router.post("")
async def create_event(req: EventCreate, user: dict = Depends(require_role("artist", "admin"))):
    if not req.is_free and (req.ticket_price is None or req.ticket_price <= 0):
        raise HTTPException(400, "Paid events need a ticket_price > 0")
    from datetime import datetime as _dt, timedelta as _td

    def make_event(start_iso: str, end_iso: Optional[str], series_id: Optional[str], seq: int, total: int) -> dict:
        return {
            "id": new_id(),
            "host_id": user["id"],
            "host_name": user["name"],
            "title": req.title,
            "description": req.description,
            "category": req.category,
            "images": [p for p in req.images if p][:8],
            "venue": req.venue, "organizer": req.organizer or user["name"],
            "website": req.website, "ticket_info": req.ticket_info, "ticket_url": req.ticket_url,
            "tags": [t.strip().lower() for t in req.tags if t.strip()][:10],
            "location": req.location.model_dump(),
            "start_at": start_iso,
            "end_at": end_iso,
            "cover_image": req.cover_image,
            "max_capacity": req.max_capacity,
            "is_free": req.is_free,
            "ticket_price": req.ticket_price if not req.is_free else None,
            "cancelled": False,
            "series_id": series_id,
            "series_seq": seq if series_id else None,
            "series_total": total if series_id else None,
            "reminders_enabled": req.reminders_enabled,
            "campus_id": campus["id"] if campus else None,
            "campus_slug": campus["slug"] if campus else None,
            "campus_name": campus["name"] if campus else None,
            "created_at": now_iso(),
        }

    campus = None
    if req.campus_id:
        from campus import _resolve as _resolve_campus
        campus = await _resolve_campus(req.campus_id)
        if not campus:
            raise HTTPException(404, "School not found")

    from engage import notify_followers_soon
    if not req.recurrence:
        e = make_event(req.start_at, req.end_at, None, 0, 1)
        await db.events.insert_one(e)
        notify_followers_soon(user["id"], "followed_new_event", f"{user['name']} announced an event", e["title"], f"/events/{e['id']}", event_id=e["id"], event_title=e["title"])
        return await _enrich(e, user)

    # Build the series
    freq_days = {"weekly": 7, "biweekly": 14, "monthly": 30}[req.recurrence.frequency]
    start_dt = _dt.fromisoformat(req.start_at.replace("Z", "+00:00"))
    end_dt = _dt.fromisoformat(req.end_at.replace("Z", "+00:00")) if req.end_at else None
    duration = (end_dt - start_dt) if end_dt else None
    series_id = new_id()
    docs = []
    for i in range(req.recurrence.count):
        st = start_dt + _td(days=freq_days * i)
        et = (st + duration) if duration else None
        docs.append(make_event(
            st.isoformat(),
            et.isoformat() if et else None,
            series_id, i + 1, req.recurrence.count,
        ))
    await db.events.insert_many(docs)
    notify_followers_soon(user["id"], "followed_new_event", f"{user['name']} announced a series", docs[0]["title"], f"/events/{docs[0]['id']}", event_id=docs[0]["id"], event_title=docs[0]["title"])
    return await _enrich(docs[0], user)


@router.get("")
async def list_events(
    upcoming_only: bool = True,
    category: Optional[str] = None,
    host_id: Optional[str] = None,
    near_lat: Optional[float] = None,
    near_lng: Optional[float] = None,
    radius_km: float = 50,
    q_search: Optional[str] = Query(default=None, alias="q"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort: str = "soonest",  # soonest | trending | distance
    saved_only: bool = False,
    free_only: bool = False,
    campus: Optional[str] = None,
    limit: int = 60,
    me: Optional[dict] = Depends(get_optional_user),
):
    limit = max(1, min(limit, 200))
    # Opportunistic reminder blast — cheap check, only sends when markers unset
    try:
        await check_event_reminders()
    except Exception:
        pass
    # Opportunistic waitlist-hold sweep — expire holds > 15min and promote next
    try:
        await _sweep_expired_holds()
    except Exception:
        pass
    q: dict = {"cancelled": {"$ne": True}}
    if category:
        if category not in EVENT_CATEGORIES:
            raise HTTPException(400, "Unknown category")
        q["category"] = category
    if host_id:
        q["host_id"] = host_id
    if upcoming_only:
        q["start_at"] = {"$gte": now_iso()}
    if date_from or date_to:
        rng = {}
        if date_from: rng["$gte"] = date_from
        if date_to: rng["$lte"] = date_to
        if upcoming_only and rng.get("$gte", "") < now_iso():
            rng["$gte"] = now_iso()
        q["start_at"] = rng
    if free_only:
        q["is_free"] = True
    if campus:
        from campus import _resolve as _resolve_campus
        c = await _resolve_campus(campus)
        q["campus_id"] = c["id"] if c else "__none__"
    if q_text := (q_search or "").strip():
        import re as _re
        rx = {"$regex": _re.escape(q_text), "$options": "i"}
        q["$or"] = [{"title": rx}, {"description": rx}, {"venue": rx}, {"organizer": rx}, {"host_name": rx},
                    {"location.city": rx}, {"location.address": rx}, {"tags": rx}]
    if saved_only:
        if not me:
            raise HTTPException(401, "Login to see saved events")
        saved_ids = [x["event_id"] for x in await db.event_saves.find({"user_id": me["id"]}, {"event_id": 1}).to_list(1000)]
        q["id"] = {"$in": saved_ids}
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
        for e in events:
            e["distance_km"] = round(dist_km(origin, (e["location"]["lat"], e["location"]["lng"])), 1)
        events = [e for e in events if e["distance_km"] <= radius_km]
        if sort == "distance":
            events.sort(key=lambda e: e["distance_km"])
    if sort == "trending":
        events.sort(key=lambda e: (e.get("rsvp_count", 0), e.get("saved_count", 0)), reverse=True)
    return events


@router.get("/meta/categories")
async def categories():
    return [{"key": k, "label": l, "color": c} for k, l, c in CATEGORY_META]


@router.get("/recommended")
async def recommended(limit: int = 6, me: dict = Depends(get_current_user)):
    """Picked for you: hosts you follow > categories/cities you've saved or attended > trending."""
    followed = {f["followed_id"] for f in await db.follows.find({"follower_id": me["id"]}, {"followed_id": 1}).to_list(2000)}
    my_ids = {r["event_id"] for r in await db.event_rsvps.find({"user_id": me["id"]}, {"event_id": 1}).to_list(2000)}
    saved_ids = {s["event_id"] for s in await db.event_saves.find({"user_id": me["id"]}, {"event_id": 1}).to_list(2000)}
    seen = my_ids | saved_ids
    liked_cats, liked_cities = {}, {}
    for e in await db.events.find({"id": {"$in": list(seen)}}, {"category": 1, "location": 1}).to_list(2000):
        liked_cats[e.get("category")] = liked_cats.get(e.get("category"), 0) + 1
        city = (e.get("location") or {}).get("city")
        if city:
            liked_cities[city] = liked_cities.get(city, 0) + 1
    cands = await db.events.find({"cancelled": {"$ne": True}, "start_at": {"$gte": now_iso()}, "host_id": {"$ne": me["id"]}}).sort("start_at", 1).limit(300).to_list(300)
    scored = []
    for e in cands:
        if e["id"] in seen:
            continue
        score, why = 0.0, []
        if e["host_id"] in followed:
            score += 3; why.append(f"{e.get('host_name', 'An artist')} — you follow them")
        if liked_cats.get(e.get("category")):
            score += 2; why.append("Matches events you've saved")
        city = (e.get("location") or {}).get("city")
        if city and liked_cities.get(city):
            score += 1; why.append(f"In {city}")
        rsvps = await db.event_rsvps.count_documents({"event_id": e["id"]})
        if rsvps >= 5:
            score += 1; why.append("Trending")
        if score > 0:
            en = await _enrich(e, me)
            en["reason"] = why[0]; en["score"] = score
            scored.append(en)
    scored.sort(key=lambda x: (-x["score"], x["start_at"]))
    out, seen_series = [], set()
    for e in scored:
        if e.get("series_id"):
            if e["series_id"] in seen_series:
                continue
            seen_series.add(e["series_id"])
        out.append(e)
    return out[:max(1, min(limit, 20))]


@router.get("/hosts/{user_id}")
async def host_page(user_id: str, me: Optional[dict] = Depends(get_optional_user)):
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(404, "Host not found")
    evs = await db.events.find({"host_id": user_id, "removed": {"$ne": True}}).sort("start_at", -1).to_list(500)
    now = now_iso()
    upcoming = [await _enrich(e, me) for e in reversed([e for e in evs if e["start_at"] >= now and not e.get("cancelled")])]
    past = [await _enrich(e, me) for e in evs if e["start_at"] < now or e.get("cancelled")]
    ev_ids = [e["id"] for e in evs]
    attendees = await db.event_rsvps.count_documents({"event_id": {"$in": ev_ids}}) if ev_ids else 0
    cfg = await db.studio_configs.find_one({"artist_id": user_id}) or {}
    return {
        "host": {"id": u["id"], "name": u["name"], "role": u.get("role"), "bio": u.get("bio"), "avatar": u.get("avatar"),
                 "cover_image": u.get("cover_image"), "location": (cfg.get("artist_story") or {}).get("location"),
                 "is_artist": u.get("role") == "artist"},
        "stats": {"events": len(evs), "upcoming": len(upcoming), "attendees": attendees,
                  "followers": await db.follows.count_documents({"followed_id": user_id}),
                  "categories": sorted({e.get("category") for e in evs if e.get("category")})},
        "is_following": bool(me and await db.follows.find_one({"follower_id": me["id"], "followed_id": user_id})),
        "upcoming": upcoming, "past": past[:30],
    }


@router.post("/{event_id}/save")
async def toggle_save(event_id: str, user: dict = Depends(get_current_user)):
    if not await db.events.find_one({"id": event_id}):
        raise HTTPException(404, "Not found")
    existing = await db.event_saves.find_one({"event_id": event_id, "user_id": user["id"]})
    if existing:
        await db.event_saves.delete_one({"id": existing["id"]})
        return {"saved": False}
    await db.event_saves.insert_one({"id": new_id(), "event_id": event_id, "user_id": user["id"], "created_at": now_iso()})
    return {"saved": True}


@router.get("/mine/saved")
async def my_saved(me: dict = Depends(get_current_user)):
    ids = [x["event_id"] for x in await db.event_saves.find({"user_id": me["id"]}).sort("created_at", -1).to_list(500)]
    evs = {e["id"]: e for e in await db.events.find({"id": {"$in": ids}}).to_list(500)}
    return [await _enrich(evs[i], me) for i in ids if i in evs]


@router.get("/{event_id}")
async def get_event(event_id: str, me: Optional[dict] = Depends(get_optional_user)):
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    return await _enrich(e, me)


@router.delete("/{event_id}")
async def cancel_event(event_id: str, cancel_series: bool = False, user: dict = Depends(get_current_user)):
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    if e["host_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not yours")
    targets = [e]
    if cancel_series and e.get("series_id"):
        # Cancel every future sibling event in the series
        siblings = await db.events.find({
            "series_id": e["series_id"],
            "cancelled": {"$ne": True},
        }).to_list(200)
        targets = siblings
    total_summary = {"cancelled": 0, "refunded": 0, "failed": 0, "amount": 0.0}
    for target in targets:
        result = await _cancel_single_event(target, user)
        total_summary["cancelled"] += 1
        total_summary["refunded"] += result.get("refunded", 0)
        total_summary["failed"] += result.get("failed", 0)
        total_summary["amount"] += result.get("amount", 0.0)
    return total_summary


async def _cancel_single_event(e: dict, user: dict) -> dict:
    event_id = e["id"]
    await db.events.update_one({"id": event_id}, {"$set": {"cancelled": True, "cancelled_at": now_iso()}})
    # Auto-refund every paid ticket
    refund_summary = {"refunded": 0, "failed": 0, "amount": 0.0}
    if not e.get("is_free"):
        try:
            import stripe as _stripe
            paid_txs = await db.payment_transactions.find({
                "kind": "event_ticket", "event_id": event_id,
                "payment_status": "paid", "refunded": {"$ne": True},
            }).to_list(2000)
            for tx in paid_txs:
                try:
                    pi = tx.get("payment_intent")
                    if not pi:
                        pi = _stripe.checkout.Session.retrieve(tx["session_id"]).payment_intent
                    try:
                        _stripe.Refund.create(payment_intent=pi, reverse_transfer=True, refund_application_fee=True)
                    except _stripe.error.InvalidRequestError:
                        _stripe.Refund.create(payment_intent=pi)
                    await db.payment_transactions.update_one(
                        {"id": tx["id"]},
                        {"$set": {"refunded": True, "refunded_at": now_iso(), "payment_status": "refunded"}},
                    )
                    await db.event_rsvps.update_one(
                        {"event_id": event_id, "user_id": tx["user_id"]},
                        {"$set": {"refunded": True, "refunded_at": now_iso()}},
                    )
                    refund_summary["refunded"] += 1
                    refund_summary["amount"] += float(tx.get("amount") or 0)
                except Exception as _re:
                    refund_summary["failed"] += 1
        except Exception:
            pass

    # Notify all RSVP'd users
    rsvps = await db.event_rsvps.find({"event_id": event_id}).to_list(2000)
    for r in rsvps:
        if r["user_id"] == user["id"]:
            continue
        was_paid = bool(r.get("paid"))
        await db.notifications.insert_one({
            "id": new_id(), "user_id": r["user_id"], "kind": "event_cancelled",
            "event_id": event_id, "event_title": e["title"],
            "refunded": was_paid,
            "amount": float(r.get("amount") or 0) if was_paid else None,
            "read": False, "created_at": now_iso(),
        })
        try:
            from push import send_push
            import asyncio as _a
            body = f"Refund of ${int(r.get('amount') or 0):,} on the way" if was_paid else e["title"]
            _a.create_task(send_push(
                r["user_id"],
                title="Event cancelled",
                body=body,
                url="/events",
                kind="event_cancelled",
            ))
        except Exception:
            pass
        # Send refund email (paid tickets only)
        if was_paid:
            try:
                from emails import send_email, refund_email_html
                from datetime import datetime as _dt
                user_doc = await db.users.find_one({"id": r["user_id"]}) or {}
                if user_doc.get("email"):
                    when = e.get("start_at", "")
                    try:
                        when = _dt.fromisoformat(when.replace("Z", "+00:00")).strftime("%b %d, %Y · %-I:%M %p")
                    except Exception:
                        pass
                    html = refund_email_html(
                        user_name=user_doc.get("name") or "there",
                        event_title=e["title"],
                        amount=float(r.get("amount") or 0),
                        event_when=when,
                    )
                    import asyncio as _a2
                    _a2.create_task(send_email(user_doc["email"], f"Refund: {e['title']}", html))
            except Exception:
                pass
    return {"cancelled": True, **refund_summary}


# ---------- Promote from waitlist when a paid RSVP gets refunded via Stripe webhook or admin ----------
async def promote_waitlist_after_refund(event_id: str):
    e = await db.events.find_one({"id": event_id})
    if not e or e.get("cancelled"):
        return
    await _promote_from_waitlist(e)


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
        # If RSVP was paid, don't auto-refund on user cancel here (only host cancel triggers refunds).
        # Promote next in waitlist if capacity is now available (only for free events; paid seats require ticket purchase from waitlist).
        if e.get("is_free"):
            await _promote_from_waitlist(e)
        return {"rsvped": False, "count": await db.event_rsvps.count_documents({"event_id": event_id})}
    # Capacity check
    if e.get("max_capacity"):
        count = await db.event_rsvps.count_documents({"event_id": event_id})
        if count >= e["max_capacity"]:
            raise HTTPException(400, "Event is full — join the waitlist")
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
        try:
            from push import send_push
            import asyncio as _a
            _a.create_task(send_push(
                e["host_id"],
                title="New RSVP",
                body=f"{user['name']} is going to {e['title']}",
                url=f"/events/{event_id}",
                kind="event_rsvp",
            ))
        except Exception:
            pass
    return {"rsvped": True, "count": await db.event_rsvps.count_documents({"event_id": event_id})}


@router.get("/{event_id}/attendees")
async def attendees(event_id: str, limit: int = 100, me: dict = Depends(get_current_user)):
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Event not found")
    is_host = me["id"] == e.get("host_id") or me.get("role") == "admin"
    cursor = db.event_rsvps.find({"event_id": event_id, "refunded": {"$ne": True}}).sort("created_at", 1).limit(min(limit, 500))
    out = []
    for r in await cursor.to_list(min(limit, 500)):
        row = {"id": r["id"], "user_id": r.get("user_id"), "user_name": r.get("user_name") or ("Gift guest" if r.get("gift") else "Guest"),
               "created_at": r.get("created_at"), "gift": bool(r.get("gift"))}
        if is_host:
            row.update({"user_email": r.get("user_email"), "paid": bool(r.get("paid")), "amount": r.get("amount"), "checked_in": bool(r.get("checked_in"))})
        out.append(row)
    return out


# ---------- Analytics (host-only) ----------
@router.get("/{event_id}/analytics")
async def event_analytics(event_id: str, user: dict = Depends(get_current_user)):
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    if e["host_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not yours")

    rsvps = await db.event_rsvps.find({"event_id": event_id}).to_list(2000)
    total = len(rsvps)
    paid = sum(1 for r in rsvps if r.get("paid"))
    refunded = sum(1 for r in rsvps if r.get("refunded"))
    checked_in = sum(1 for r in rsvps if r.get("checked_in"))
    revenue_gross = sum(float(r.get("amount") or 0) for r in rsvps if r.get("paid") and not r.get("refunded"))
    revenue_refunded = sum(float(r.get("amount") or 0) for r in rsvps if r.get("refunded"))

    # Fee estimate: seller-pays-processing split from platform settings
    try:
        from payments import get_settings as _gs, split_amount as _split
        _settings = await _gs()
        _sp = _split(revenue_gross, _settings)
        est_platform_fee = _sp["platform_take"] + _sp["processing_fee"]
        net_to_host = _sp["net"]
    except Exception:
        est_platform_fee = revenue_gross * 0.04
        net_to_host = max(0.0, revenue_gross - est_platform_fee)

    # RSVP curve — count per day since creation
    try:
        created = _dt.fromisoformat(e["created_at"].replace("Z", "+00:00"))
    except Exception:
        created = _dt.now(_tz.utc) - _td(days=30)
    today = _dt.now(_tz.utc).date()
    days = max(1, (today - created.date()).days + 1)
    days = min(days, 60)  # cap chart to 60 days
    buckets = {}
    for i in range(days):
        d = today - _td(days=days - 1 - i)
        buckets[d.isoformat()] = 0
    for r in rsvps:
        try:
            d = _dt.fromisoformat(r["created_at"].replace("Z", "+00:00")).date().isoformat()
            if d in buckets:
                buckets[d] += 1
        except Exception:
            continue
    curve = [{"date": k, "count": v} for k, v in buckets.items()]

    waitlist_count = await db.event_waitlist.count_documents({"event_id": event_id, "notified": False})

    return {
        "event_id": event_id,
        "title": e["title"],
        "start_at": e.get("start_at"),
        "total_rsvps": total,
        "paid_rsvps": paid,
        "free_rsvps": total - paid,
        "refunded_rsvps": refunded,
        "checked_in": checked_in,
        "check_in_rate": round((checked_in / total) * 100.0, 1) if total else 0.0,
        "capacity": e.get("max_capacity"),
        "fill_rate": round((total / e["max_capacity"]) * 100.0, 1) if e.get("max_capacity") else None,
        "waitlist": waitlist_count,
        "revenue_gross": round(revenue_gross, 2),
        "revenue_refunded": round(revenue_refunded, 2),
        "platform_fee": round(est_platform_fee, 2),
        "net_to_host": round(net_to_host, 2),
        "rsvp_curve": curve,
    }


# ---------- Analytics CSV Export ----------
@router.get("/{event_id}/analytics.csv")
async def event_analytics_csv(event_id: str, kind: str = "attendees", user: dict = Depends(get_current_user)):
    """Downloadable CSV. kind ∈ {'attendees', 'revenue'}."""
    from fastapi.responses import PlainTextResponse
    import csv
    import io as _io

    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    if e["host_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not yours")
    if kind not in ("attendees", "revenue"):
        raise HTTPException(400, "kind must be 'attendees' or 'revenue'")

    buf = _io.StringIO()

    class _SafeWriter:
        """Neutralise spreadsheet formula injection (cells starting with = + - @ or tab/CR)."""
        def __init__(self, w): self._w = w

        def writerow(self, row):
            self._w.writerow([("'" + v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v for v in row])

    writer = _SafeWriter(csv.writer(buf))
    safe_title = "".join(c for c in e["title"] if c.isalnum() or c in " -_")[:40].strip().replace(" ", "_")

    if kind == "attendees":
        writer.writerow(["Name", "Email", "RSVP Date", "Paid", "Amount", "Refunded", "Checked In", "Checked In At"])
        rsvps = await db.event_rsvps.find({"event_id": event_id}).sort("created_at", 1).to_list(5000)
        for r in rsvps:
            user_doc = await db.users.find_one({"id": r["user_id"]}) or {}
            writer.writerow([
                r.get("user_name") or user_doc.get("name") or "",
                user_doc.get("email") or "",
                r.get("created_at", ""),
                "Yes" if r.get("paid") else "No",
                r.get("amount") or "",
                "Yes" if r.get("refunded") else "No",
                "Yes" if r.get("checked_in") else "No",
                r.get("checked_in_at") or "",
            ])
        filename = f"artcore_attendees_{safe_title}.csv"
    else:
        writer.writerow(["Transaction ID", "Buyer Email", "Amount", "Currency", "Status", "Payment Intent", "Refunded", "Date"])
        txs = await db.payment_transactions.find({
            "kind": "event_ticket", "event_id": event_id,
        }).sort("created_at", 1).to_list(5000)
        for t in txs:
            buyer = await db.users.find_one({"id": t.get("user_id")}) or {}
            writer.writerow([
                t.get("id", ""),
                buyer.get("email") or "",
                t.get("amount") or 0,
                t.get("currency", "usd"),
                t.get("payment_status", "unknown"),
                t.get("payment_intent") or "",
                "Yes" if t.get("refunded") else "No",
                t.get("created_at", ""),
            ])
        filename = f"artcore_revenue_{safe_title}.csv"

    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


# ---------- Waitlist ----------
@router.post("/{event_id}/waitlist")
async def join_waitlist(event_id: str, user: dict = Depends(get_current_user)):
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    if e.get("cancelled"):
        raise HTTPException(400, "Event was cancelled")
    if not e.get("max_capacity"):
        raise HTTPException(400, "This event has no capacity limit")
    # Already RSVP'd?
    if await db.event_rsvps.find_one({"event_id": event_id, "user_id": user["id"]}):
        raise HTTPException(400, "You already have a ticket")
    # Already on the list?
    existing = await db.event_waitlist.find_one({"event_id": event_id, "user_id": user["id"]})
    if existing:
        await db.event_waitlist.delete_one({"_id": existing["_id"]})
        return {"on_waitlist": False, "position": None}
    await db.event_waitlist.insert_one({
        "id": new_id(), "event_id": event_id, "user_id": user["id"],
        "user_name": user["name"], "user_email": user.get("email"),
        "notified": False, "created_at": now_iso(),
    })
    position = await db.event_waitlist.count_documents({"event_id": event_id, "notified": False})
    # Confirmation email: "you're #N on the waitlist"
    if user.get("email"):
        try:
            from emails import send_email, waitlist_position_html
            import asyncio as _a
            _a.create_task(send_email(user["email"], f"You're #{position} on the waitlist: {e['title']}",
                                      waitlist_position_html(user["name"], strip_mongo(e), position)))
        except Exception:
            pass
    await db.notifications.insert_one({
        "id": new_id(), "user_id": user["id"], "kind": "event_waitlist_joined",
        "event_id": event_id, "event_title": e["title"], "position": position,
        "read": False, "created_at": now_iso(),
    })
    return {"on_waitlist": True, "position": position}


@router.get("/{event_id}/waitlist")
async def list_waitlist(event_id: str, user: dict = Depends(get_current_user)):
    """Host-only summary of who's on the waitlist."""
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    if e["host_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not yours")
    cursor = db.event_waitlist.find({"event_id": event_id}).sort("created_at", 1).limit(200)
    return [strip_mongo(r) for r in await cursor.to_list(200)]


async def _sweep_expired_holds():
    """Expire waitlist holds that passed their 15-min TTL without payment, and promote next."""
    from datetime import datetime as _dt, timezone as _tz
    now_iso_str = _dt.now(_tz.utc).isoformat()
    stale = await db.waitlist_holds.find({
        "claimed": False, "expired": False, "expires_at_iso": {"$lt": now_iso_str},
    }).to_list(50)
    for h in stale:
        await db.waitlist_holds.update_one({"_id": h["_id"]}, {"$set": {"expired": True}})
        # Also expire the pending transaction
        await db.payment_transactions.update_one(
            {"session_id": h["session_id"], "payment_status": "pending"},
            {"$set": {"payment_status": "expired", "updated_at": now_iso()}},
        )
        # Promote the next person on the waitlist
        ev = await db.events.find_one({"id": h["event_id"]})
        if ev and not ev.get("cancelled"):
            await _promote_from_waitlist(ev)



async def _promote_from_waitlist(e: dict) -> Optional[dict]:
    """Notify the next un-notified user on the waitlist that a seat opened up.
    For PAID events: creates a 15-min Stripe hold checkout link (auto-charge experience).
    For FREE events: sends a plain invite to RSVP.
    """
    if not e.get("max_capacity"):
        return None
    filled = await db.event_rsvps.count_documents({"event_id": e["id"]})
    if filled >= e["max_capacity"]:
        return None
    # Check for a still-valid unclaimed hold — if so, don't promote yet
    from datetime import datetime as _dt, timezone as _tz
    now = _dt.now(_tz.utc)
    hold = await db.waitlist_holds.find_one({
        "event_id": e["id"], "claimed": False, "expired": False,
        "expires_at_iso": {"$gt": now.isoformat()},
    })
    if hold:
        return None
    nxt = await db.event_waitlist.find_one({"event_id": e["id"], "notified": False}, sort=[("created_at", 1)])
    if not nxt:
        return None
    await db.event_waitlist.update_one({"_id": nxt["_id"]}, {"$set": {"notified": True, "notified_at": now_iso()}})

    checkout_url = None
    hold_expires_at = None
    if not e.get("is_free"):
        # Create a 15-minute-expiring Stripe checkout session for this reserved seat
        try:
            import stripe as _stripe
            import os as _os
            from datetime import timedelta as _td
            settings_row = await db.settings.find_one({"id": "global"}) or {}
            currency = settings_row.get("currency", "usd")
            from connect import build_transfer_options
            transfer_kwargs = await build_transfer_options(e["host_id"], float(e["ticket_price"]))
            expires_ts = int((now + _td(minutes=15)).timestamp())
            origin = _os.environ.get("PUBLIC_APP_URL", "https://artcorestudio.net")
            session = _stripe.checkout.Session.create(
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": currency,
                        "product_data": {"name": f"Reserved Ticket: {e['title']}"},
                        "unit_amount": int(round(float(e["ticket_price"]) * 100)),
                    },
                    "quantity": 1,
                }],
                success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{origin}/events/{e['id']}",
                customer_email=nxt.get("user_email") or None,
                expires_at=expires_ts,
                metadata={"kind": "event_ticket", "event_id": e["id"], "user_id": nxt["user_id"], "waitlist_hold": "1"},
                **transfer_kwargs,
            )
            hold_expires_at = (now + _td(minutes=15)).isoformat()
            await db.waitlist_holds.insert_one({
                "id": new_id(), "event_id": e["id"], "user_id": nxt["user_id"],
                "session_id": session.id, "created_at": now_iso(),
                "expires_at_iso": hold_expires_at, "claimed": False, "expired": False,
            })
            await db.payment_transactions.insert_one({
                "id": new_id(), "session_id": session.id,
                "kind": "event_ticket", "user_id": nxt["user_id"],
                "event_id": e["id"], "host_id": e["host_id"],
                "amount": float(e["ticket_price"]), "currency": currency,
                "status": "initiated", "payment_status": "pending", "waitlist_hold": True,
                "created_at": now_iso(), "updated_at": now_iso(),
            })
            checkout_url = session.url
        except Exception as _e:
            log.warning("Waitlist hold creation failed: %s", _e)
            checkout_url = None

    await db.notifications.insert_one({
        "id": new_id(), "user_id": nxt["user_id"], "kind": "event_waitlist_open",
        "event_id": e["id"], "event_title": e["title"], "is_free": bool(e.get("is_free")),
        "ticket_price": e.get("ticket_price"),
        "checkout_url": checkout_url, "hold_expires_at": hold_expires_at,
        "read": False, "created_at": now_iso(),
    })
    # Push
    try:
        from push import send_push
        import asyncio as _a
        if e.get("is_free"):
            body = "A seat opened up — RSVP now"
        else:
            body = f"Seat reserved 15min: ${int(e['ticket_price'] or 0):,} · Tap to pay"
        _a.create_task(send_push(
            nxt["user_id"],
            title=f"You're off the waitlist: {e['title']}",
            body=body,
            url=checkout_url or f"/events/{e['id']}",
            kind="event_waitlist_open",
        ))
    except Exception:
        pass
    # Email invite
    try:
        from emails import send_email
        html = _waitlist_invite_html(nxt.get("user_name") or "there", e, checkout_url=checkout_url, hold_expires_at=hold_expires_at)
        import asyncio as _a2
        if nxt.get("user_email"):
            _a2.create_task(send_email(nxt["user_email"], f"A seat opened up: {e['title']}", html))
    except Exception:
        pass
    return nxt


def _waitlist_invite_html(user_name: str, e: dict, checkout_url: Optional[str] = None, hold_expires_at: Optional[str] = None) -> str:
    from emails import _wrap
    import html as _h
    user_name = _h.escape(user_name or "")
    e = {**e, "title": _h.escape(str(e.get("title") or ""))}
    price = f"${e['ticket_price']:,.2f}" if not e.get("is_free") else "Free"
    cta_href = checkout_url or f"https://artcorestudio.net/events/{e['id']}"
    cta_label = "Complete payment (15 min)" if checkout_url else "Claim your seat"
    countdown_note = ""
    if hold_expires_at and checkout_url:
        countdown_note = f"<div style=\"font-size:12px;color:#F5A623;margin-bottom:16px\">⏱ Your seat is held for 15 minutes.</div>"
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  A seat opened up
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:24px">
  Hey {user_name}, a spot just opened for <strong style="color:#fff">{e['title']}</strong>.
</div>
{countdown_note}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="background:rgba(204,255,0,0.08);border:1px solid rgba(204,255,0,0.3);border-radius:4px;margin-bottom:24px">
  <tr><td style="padding:20px">
    <div style="font-size:11px;color:#CCFF00;letter-spacing:2px;text-transform:uppercase">Your invite</div>
    <div style="font-family:Impact,Arial Black,sans-serif;font-size:24px;color:#fff;margin-top:6px">{e['title']}</div>
    <div style="font-size:12px;color:#a1a1aa;margin-top:10px">Price: {price}</div>
  </td></tr>
</table>

<div style="margin-top:28px">
  <a href="{cta_href}" style="display:inline-block;background:#CCFF00;color:#000;
     padding:12px 22px;text-decoration:none;font-family:Impact,Arial Black,sans-serif;
     letter-spacing:1px;text-transform:uppercase;font-size:13px;border-radius:2px">
    {cta_label} →
  </a>
</div>
"""
    return _wrap(body, "Waitlist Invite")


@router.get("/mine/tickets")
async def my_tickets(upcoming_only: bool = True, user: dict = Depends(get_current_user)):
    """Return every RSVP the current user has (upcoming by default), enriched with event data."""
    rsvps = await db.event_rsvps.find({"user_id": user["id"]}).sort("created_at", -1).to_list(500)
    tickets = []
    for r in rsvps:
        e = await db.events.find_one({"id": r["event_id"]})
        if not e:
            continue
        if upcoming_only and e.get("start_at", "") < now_iso() and not e.get("cancelled"):
            continue
        tickets.append({
            "rsvp_id": r["id"],
            "event": strip_mongo(e),
            "paid": bool(r.get("paid")),
            "amount": r.get("amount"),
            "refunded": bool(r.get("refunded")),
            "checked_in": bool(r.get("checked_in")),
            "checked_in_at": r.get("checked_in_at"),
            "qr_payload": f"artcore:ticket:{r['id']}:{r['event_id']}",
            "created_at": r["created_at"],
        })
    # Sort by upcoming date first
    tickets.sort(key=lambda t: t["event"].get("start_at", ""))
    return tickets


# ---------- Series editing ----------
class EventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=140)
    description: Optional[str] = Field(default=None, min_length=3, max_length=4000)
    category: Optional[str] = None
    location: Optional[Location] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    cover_image: Optional[str] = None
    max_capacity: Optional[int] = Field(default=None, ge=1, le=100000)
    is_free: Optional[bool] = None
    ticket_price: Optional[float] = Field(default=None, ge=0)
    reminders_enabled: Optional[bool] = None
    images: Optional[List[str]] = None
    venue: Optional[str] = Field(default=None, max_length=200)
    organizer: Optional[str] = Field(default=None, max_length=200)
    website: Optional[str] = Field(default=None, max_length=500)
    ticket_info: Optional[str] = Field(default=None, max_length=500)
    ticket_url: Optional[str] = Field(default=None, max_length=500)
    tags: Optional[List[str]] = None
    campus_id: Optional[str] = None
    apply_to: str = "this"  # "this" | "series"

    @field_validator("category")
    @classmethod
    def _check_cat(cls, v):
        if v is not None and v not in EVENT_CATEGORIES:
            raise ValueError(f"Category must be one of {EVENT_CATEGORIES}")
        return v

    @field_validator("apply_to")
    @classmethod
    def _check_scope(cls, v):
        if v not in ("this", "series"):
            raise ValueError("apply_to must be 'this' or 'series'")
        return v


@router.patch("/{event_id}")
async def edit_event(event_id: str, req: EventUpdate, user: dict = Depends(get_current_user)):
    e = await db.events.find_one({"id": event_id})
    if not e:
        raise HTTPException(404, "Not found")
    if e["host_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not yours")

    # Build the patch dict from non-None fields
    patch: dict = {}
    if req.title is not None: patch["title"] = req.title
    if req.description is not None: patch["description"] = req.description
    if req.category is not None: patch["category"] = req.category
    if req.location is not None: patch["location"] = req.location.model_dump()
    if req.cover_image is not None: patch["cover_image"] = req.cover_image
    if req.max_capacity is not None: patch["max_capacity"] = req.max_capacity
    if req.is_free is not None: patch["is_free"] = req.is_free
    if req.ticket_price is not None: patch["ticket_price"] = req.ticket_price
    if req.reminders_enabled is not None: patch["reminders_enabled"] = req.reminders_enabled
    for k in ("images", "venue", "organizer", "website", "ticket_info", "ticket_url", "tags"):
        v = getattr(req, k)
        if v is not None:
            if k in ("website", "ticket_url") and v and not v.startswith(("http://", "https://")):
                v = "https://" + v
            patch[k] = v
    if "campus_id" in req.model_fields_set:
        if req.campus_id:
            from campus import _resolve as _resolve_campus
            c = await _resolve_campus(req.campus_id)
            if not c:
                raise HTTPException(404, "School not found")
            patch.update({"campus_id": c["id"], "campus_slug": c["slug"], "campus_name": c["name"]})
        else:
            patch.update({"campus_id": None, "campus_slug": None, "campus_name": None})
    # is_free/ticket_price consistency
    if patch.get("is_free") is True:
        patch["ticket_price"] = None
    elif patch.get("is_free") is False and (patch.get("ticket_price") or 0) <= 0:
        raise HTTPException(400, "Paid events need a ticket_price > 0")

    updated = 0
    if req.apply_to == "series" and e.get("series_id"):
        # Update every future sibling, but keep each occurrence's own start/end
        siblings = await db.events.find({
            "series_id": e["series_id"], "cancelled": {"$ne": True},
        }).to_list(200)
        for s in siblings:
            r = await db.events.update_one({"id": s["id"]}, {"$set": patch})
            updated += r.modified_count
    else:
        # Single event — allow start/end changes
        if req.start_at is not None: patch["start_at"] = req.start_at
        if req.end_at is not None: patch["end_at"] = req.end_at
        r = await db.events.update_one({"id": event_id}, {"$set": patch})
        updated = r.modified_count

    return {"updated": updated, "apply_to": req.apply_to}


@router.get("/lists/trending")
async def trending_events(
    limit: int = 12,
    near_lat: Optional[float] = None,
    near_lng: Optional[float] = None,
    radius_km: float = 100,
    me: Optional[dict] = Depends(get_optional_user),
):
    """Rank upcoming events by hotness = recent RSVPs (48h) weighted by proximity to event date."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    now = _dt.now(_tz.utc)
    horizon = (now - _td(hours=48)).isoformat()
    upcoming_iso = now.isoformat()

    cursor = db.events.find({
        "cancelled": {"$ne": True},
        "start_at": {"$gte": upcoming_iso},
    }).limit(300)
    events = await cursor.to_list(300)

    scored = []
    for e in events:
        recent = await db.event_rsvps.count_documents({
            "event_id": e["id"], "created_at": {"$gte": horizon},
        })
        total = await db.event_rsvps.count_documents({"event_id": e["id"]})
        # Boost events that are soon (within a week gets extra weight)
        try:
            start = _dt.fromisoformat(e["start_at"].replace("Z", "+00:00"))
            days_out = max(0.5, (start - now).total_seconds() / 86400.0)
            soon_boost = 1.0 + max(0.0, 1.0 - min(days_out, 7) / 7.0)  # 2.0 for tomorrow → 1.0 for 7+ days
        except Exception:
            soon_boost = 1.0
        score = (recent * 3.0 + total * 1.0) * soon_boost
        scored.append((score, recent, e))

    # Optional distance filter
    if near_lat is not None and near_lng is not None:
        import math

        def dist_km(a, b):
            R = 6371.0
            dlat = math.radians(b[0] - a[0])
            dlng = math.radians(b[1] - a[1])
            aa = (math.sin(dlat / 2) ** 2
                  + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0]))
                  * math.sin(dlng / 2) ** 2)
            return 2 * R * math.asin(math.sqrt(aa))
        origin = (near_lat, near_lng)
        scored = [t for t in scored if dist_km(origin, (t[2]["location"]["lat"], t[2]["location"]["lng"])) <= radius_km]

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[: max(1, min(limit, 40))]
    out = []
    for score, recent, e in top:
        enriched = await _enrich(e, me)
        enriched["trend_score"] = round(score, 2)
        enriched["recent_rsvps_48h"] = recent
        out.append(enriched)
    return out


# ---------- Ticket QR ----------
def _qr_png(payload: str) -> Optional[bytes]:
    try:
        import qrcode as _qr
        import io as _io
        img = _qr.make(payload, box_size=10, border=2)
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


@router.get("/gift/{token}")
async def gift_ticket(token: str):
    """Public gift ticket view (no auth) — the recipient opens this from their email."""
    rsvp = await db.event_rsvps.find_one({"gift_token": token})
    if not rsvp:
        raise HTTPException(404, "Gift ticket not found")
    ev = await db.events.find_one({"id": rsvp["event_id"]})
    if not ev:
        raise HTTPException(404, "Event not found")
    payload = f"artcore:ticket:{rsvp['id']}:{rsvp['event_id']}"
    png = _qr_png(payload)
    import base64 as _b64
    return {
        "rsvp_id": rsvp["id"],
        "event": {"id": ev["id"], "title": ev["title"], "start_at": ev.get("start_at"), "location": ev.get("location"), "cover_image": ev.get("cover_image"), "cancelled": bool(ev.get("cancelled"))},
        "user_name": rsvp.get("user_name"),
        "gifted_by_name": rsvp.get("gifted_by_name"),
        "gift_message": rsvp.get("gift_message"),
        "refunded": bool(rsvp.get("refunded")),
        "checked_in": bool(rsvp.get("checked_in")),
        "claimed": bool(rsvp.get("user_id")),
        "qr_payload": payload,
        "qr_image": f"data:image/png;base64,{_b64.b64encode(png).decode()}" if png else None,
    }


def _pass_response(png: bytes, filename: str):
    from fastapi.responses import Response
    return Response(content=png, media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, max-age=3600"})


def _where(ev: dict) -> str:
    loc = ev.get("location") or {}
    return ", ".join([x for x in [loc.get("venue"), loc.get("address"), loc.get("city")] if x]) or "TBA"


@router.get("/gift/{token}/pass.png")
async def gift_ticket_pass(token: str):
    from wallet_pass import render_pass
    rsvp = await db.event_rsvps.find_one({"gift_token": token})
    if not rsvp:
        raise HTTPException(404, "Gift ticket not found")
    ev = await db.events.find_one({"id": rsvp["event_id"]}) or {}
    png = render_pass(ev.get("title", "Event"), ev.get("start_at", ""), _where(ev), rsvp.get("user_name") or "Guest",
                      _qr_png(f"artcore:ticket:{rsvp['id']}:{rsvp['event_id']}"), rsvp["id"], subtitle="Gift ticket")
    return _pass_response(png, f"artcore-ticket-{rsvp['id'][:8]}.png")


@router.get("/{event_id}/my-ticket/pass.png")
async def my_ticket_pass(event_id: str, user: dict = Depends(get_current_user)):
    from wallet_pass import render_pass
    ev = await db.events.find_one({"id": event_id})
    rsvp = await db.event_rsvps.find_one({"event_id": event_id, "user_id": user["id"]})
    if not ev or not rsvp:
        raise HTTPException(404, "You don't have a ticket for this event")
    if rsvp.get("refunded") or ev.get("cancelled"):
        raise HTTPException(400, "Ticket is no longer valid")
    png = render_pass(ev["title"], ev.get("start_at", ""), _where(ev), rsvp.get("user_name") or user["name"],
                      _qr_png(f"artcore:ticket:{rsvp['id']}:{event_id}"), rsvp["id"])
    return _pass_response(png, f"artcore-ticket-{rsvp['id'][:8]}.png")


@router.get("/gift/{token}/qr.png")
async def gift_ticket_qr(token: str):
    from fastapi.responses import Response
    rsvp = await db.event_rsvps.find_one({"gift_token": token})
    if not rsvp:
        raise HTTPException(404, "Gift ticket not found")
    png = _qr_png(f"artcore:ticket:{rsvp['id']}:{rsvp['event_id']}")
    if not png:
        raise HTTPException(500, "QR unavailable")
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/{event_id}/my-ticket")
async def my_ticket(event_id: str, user: dict = Depends(get_current_user)):
    """Returns a scannable QR code + ticket metadata for the current user."""
    ev = await db.events.find_one({"id": event_id})
    if not ev:
        raise HTTPException(404, "Not found")
    rsvp = await db.event_rsvps.find_one({"event_id": event_id, "user_id": user["id"]})
    if not rsvp:
        raise HTTPException(404, "You don't have a ticket for this event")
    if ev.get("cancelled"):
        raise HTTPException(400, "Event was cancelled")
    if rsvp.get("refunded"):
        raise HTTPException(400, "Ticket was refunded")
    # Build QR payload — verifiable by the check-in endpoint
    payload = f"artcore:ticket:{rsvp['id']}:{event_id}"
    try:
        import qrcode as _qr
        import io as _io, base64 as _b64
        img = _qr.make(payload, box_size=10, border=2)
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = _b64.b64encode(buf.getvalue()).decode()
    except Exception:
        qr_b64 = None
    return {
        "rsvp_id": rsvp["id"],
        "event_id": event_id,
        "event_title": ev["title"],
        "event_start_at": ev["start_at"],
        "location": ev["location"],
        "user_name": rsvp.get("user_name", user["name"]),
        "paid": bool(rsvp.get("paid")),
        "amount": rsvp.get("amount"),
        "checked_in": bool(rsvp.get("checked_in")),
        "checked_in_at": rsvp.get("checked_in_at"),
        "qr_payload": payload,
        "qr_image": f"data:image/png;base64,{qr_b64}" if qr_b64 else None,
    }


class CheckInReq(BaseModel):
    qr_payload: str


@router.post("/{event_id}/check-in")
async def check_in(event_id: str, req: CheckInReq, user: dict = Depends(get_current_user)):
    """Host / admin scans a QR to check an attendee in."""
    ev = await db.events.find_one({"id": event_id})
    if not ev:
        raise HTTPException(404, "Event not found")
    if ev["host_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Only the host can check attendees in")
    parts = (req.qr_payload or "").split(":")
    if len(parts) != 4 or parts[0] != "artcore" or parts[1] != "ticket":
        raise HTTPException(400, "Invalid QR payload")
    rsvp_id, ticket_event_id = parts[2], parts[3]
    if ticket_event_id != event_id:
        raise HTTPException(400, "Ticket is for a different event")
    rsvp = await db.event_rsvps.find_one({"id": rsvp_id, "event_id": event_id})
    if not rsvp:
        raise HTTPException(404, "Ticket not recognized")
    if rsvp.get("refunded"):
        raise HTTPException(400, "Ticket was refunded")
    if rsvp.get("checked_in"):
        return {"ok": True, "already": True, "user_name": rsvp.get("user_name"), "checked_in_at": rsvp.get("checked_in_at")}
    await db.event_rsvps.update_one({"id": rsvp_id}, {"$set": {"checked_in": True, "checked_in_at": now_iso()}})
    return {"ok": True, "user_name": rsvp.get("user_name"), "checked_in_at": now_iso()}


# ---------- Host broadcast to attendees (DM + email + push) ----------
class BroadcastReq(BaseModel):
    subject: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=2, max_length=2000)
    via_dm: bool = True
    via_email: bool = True
    include_waitlist: bool = False


@router.post("/{event_id}/broadcast")
async def broadcast(event_id: str, req: BroadcastReq, user: dict = Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id})
    if not ev:
        raise HTTPException(404, "Not found")
    if ev["host_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Only the host can message attendees")
    if not req.via_dm and not req.via_email:
        raise HTTPException(400, "Pick at least one channel")

    recipients: dict = {}
    for r in await db.event_rsvps.find({"event_id": event_id, "refunded": {"$ne": True}}).to_list(5000):
        recipients[r["user_id"]] = "attendee"
    if req.include_waitlist:
        for w in await db.event_waitlist.find({"event_id": event_id}).to_list(2000):
            recipients.setdefault(w["user_id"], "waitlist")
    recipients.pop(user["id"], None)

    from messages import deliver_dm
    from emails import send_email, event_broadcast_html
    from push import send_push
    import asyncio as _a
    ev_clean = strip_mongo(ev)
    dm_text = f"📣 {req.subject}\n\n{req.message}\n\nEvent: {ev['title']}"
    sent = {"recipients": len(recipients), "dm": 0, "email": 0}

    async def _deliver(uid: str):
        u = await db.users.find_one({"id": uid})
        if not u:
            return
        if req.via_dm:
            try:
                await deliver_dm(user, uid, dm_text, notify=False)
                sent["dm"] += 1
            except Exception:
                pass
        if req.via_email and u.get("email"):
            _a.create_task(send_email(u["email"], f"{ev['title']}: {req.subject}",
                                      event_broadcast_html(u["name"], user["name"], ev_clean, req.subject, req.message)))
            sent["email"] += 1
        await db.notifications.insert_one({
            "id": new_id(), "user_id": uid, "kind": "event_broadcast",
            "event_id": event_id, "event_title": ev["title"],
            "from_user_id": user["id"], "from_user_name": user["name"],
            "preview": f"{req.subject} — {req.message}"[:140],
            "read": False, "created_at": now_iso(),
        })
        _a.create_task(send_push(uid, title=f"{ev['title']}: {req.subject}", body=req.message[:140],
                                 url=f"/events/{event_id}", kind="event_broadcast"))

    await _a.gather(*(_deliver(uid) for uid in recipients))

    record = {
        "id": new_id(), "event_id": event_id, "host_id": user["id"], "host_name": user["name"],
        "subject": req.subject, "message": req.message, "via_dm": req.via_dm, "via_email": req.via_email,
        "include_waitlist": req.include_waitlist, **sent, "created_at": now_iso(),
    }
    await db.event_broadcasts.insert_one(record)
    return strip_mongo(record)


@router.get("/{event_id}/broadcasts")
async def list_broadcasts(event_id: str, user: dict = Depends(get_current_user)):
    ev = await db.events.find_one({"id": event_id})
    if not ev:
        raise HTTPException(404, "Not found")
    if ev["host_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not yours")
    cursor = db.event_broadcasts.find({"event_id": event_id}).sort("created_at", -1).limit(50)
    return [strip_mongo(b) for b in await cursor.to_list(50)]


# ---------- Reminder scheduler ----------
async def check_event_reminders():
    """Fire push at 24h and 1h before start_at. Idempotent via marker fields on the event."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    now = _dt.now(_tz.utc)
    horizon = (now + _td(hours=25)).isoformat()
    cursor = db.events.find({
        "cancelled": {"$ne": True},
        "start_at": {"$gte": now.isoformat(), "$lte": horizon},
    })
    events = await cursor.to_list(200)
    for e in events:
        if e.get("reminders_enabled") is False:
            continue
        try:
            start = _dt.fromisoformat(e["start_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        delta = start - now
        marker_1h = e.get("reminder_1h_sent")
        marker_24h = e.get("reminder_24h_sent")
        # 1h window (fire once when < 1h remains)
        if _td(seconds=0) < delta <= _td(hours=1) and not marker_1h:
            await _blast_reminder(e, "starts in under 1 hour", "1h")
        # 24h window (fire once when between 22h and 25h remains)
        elif _td(hours=22) <= delta <= _td(hours=25) and not marker_24h:
            await _blast_reminder(e, "starts tomorrow", "24h")


async def _blast_reminder(e: dict, tail: str, marker: str):
    """Notify every RSVP'd user + set the marker on the event."""
    await db.events.update_one({"id": e["id"]}, {"$set": {f"reminder_{marker}_sent": now_iso()}})
    rsvps = await db.event_rsvps.find({"event_id": e["id"], "refunded": {"$ne": True}}).to_list(2000)
    for r in rsvps:
        if r.get("gift") and r.get("gift_email") and marker == "24h" and not r.get("gift_reminder_sent"):
            await _email_gift_reminder(e, r)
        if not r.get("user_id"):
            continue
        await db.notifications.insert_one({
            "id": new_id(), "user_id": r["user_id"], "kind": "event_reminder",
            "event_id": e["id"], "event_title": e["title"],
            "read": False, "created_at": now_iso(),
        })
        try:
            from push import send_push
            import asyncio as _a
            _a.create_task(send_push(
                r["user_id"],
                title=e["title"],
                body=f"Event {tail} — {e['location'].get('city') or e['location'].get('address') or 'see details'}",
                url=f"/events/{e['id']}",
                kind="event_reminder",
            ))
        except Exception:
            pass


async def _email_gift_reminder(e: dict, r: dict):
    """Day-before email to a gift-ticket recipient with their QR — idempotent via rsvp marker."""
    import os as _os
    await db.event_rsvps.update_one({"id": r["id"]}, {"$set": {"gift_reminder_sent": now_iso()}})
    try:
        from emails import send_email, gift_reminder_html, _fmt_when
        origin = _os.environ.get("PUBLIC_APP_URL", "https://artcorestudio.net")
        loc = e.get("location") or {}
        html = gift_reminder_html(
            r.get("user_name") or "there", e["title"], _fmt_when(e.get("start_at", "")),
            loc.get("city") or loc.get("address") or "TBA",
            f"{origin}/gift/{r['gift_token']}", f"{origin}/api/events/gift/{r['gift_token']}/qr.png",
        )
        import asyncio as _a
        _a.create_task(send_email(r["gift_email"], f"Tomorrow: {e['title']} — your ticket", html))
    except Exception:
        pass
