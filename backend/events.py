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
    # Opportunistic reminder blast — cheap check, only sends when markers unset
    try:
        await check_event_reminders()
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
    await db.events.update_one({"id": event_id}, {"$set": {"cancelled": True, "cancelled_at": now_iso()}})

    # Auto-refund every paid ticket
    refund_summary = {"refunded": 0, "failed": 0, "amount": 0.0}
    if not e.get("is_free"):
        try:
            import os as _os, stripe as _stripe
            _stripe.api_key = _os.environ["STRIPE_SECRET_KEY"]
            paid_txs = await db.payment_transactions.find({
                "kind": "event_ticket", "event_id": event_id,
                "payment_status": "paid", "refunded": {"$ne": True},
            }).to_list(2000)
            for tx in paid_txs:
                try:
                    _stripe.Refund.create(
                        payment_intent=tx.get("payment_intent"),
                        checkout_session=tx.get("session_id") if not tx.get("payment_intent") else None,
                        reverse_transfer=True,
                        refund_application_fee=True,
                    ) if tx.get("payment_intent") else _stripe.checkout.Session.retrieve(tx["session_id"], expand=["payment_intent"])
                    # If we don't have payment_intent stored, retrieve+refund
                    if not tx.get("payment_intent"):
                        s = _stripe.checkout.Session.retrieve(tx["session_id"])
                        pi = s.payment_intent
                        _stripe.Refund.create(payment_intent=pi, reverse_transfer=True, refund_application_fee=True)
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
async def attendees(event_id: str, limit: int = 100):
    cursor = db.event_rsvps.find({"event_id": event_id}).sort("created_at", 1).limit(limit)
    return [strip_mongo(r) for r in await cursor.to_list(limit)]


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


# ---------- Trending (by RSVP velocity) ----------
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
    rsvps = await db.event_rsvps.find({"event_id": e["id"]}).to_list(2000)
    for r in rsvps:
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
