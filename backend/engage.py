"""Follow alerts (fan-out to followers), Staff Picks, and personal calendar feeds."""
import asyncio
import os
import secrets
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, require_role

router = APIRouter(prefix="/api", tags=["engage"])
APP_URL = os.environ.get("PUBLIC_APP_URL", "https://artcorestudio.net")


# ---------- Follow alerts ----------
async def notify_followers(artist_id: str, kind: str, title: str, body: str, url: str, **extra):
    """In-app + push to everyone following `artist_id`. kinds: followed_new_artwork | followed_new_post | followed_new_event."""
    from push import send_push
    artist = await db.users.find_one({"id": artist_id}) or {}
    followers = [f["follower_id"] for f in await db.follows.find({"followed_id": artist_id}, {"follower_id": 1}).to_list(10000)]
    if not followers:
        return 0
    docs = [{"id": new_id(), "user_id": uid, "kind": kind, "from_user_id": artist_id, "from_user_name": artist.get("name"),
             "read": False, "created_at": now_iso(), **extra} for uid in followers]
    await db.notifications.insert_many(docs)
    for uid in followers:
        asyncio.create_task(send_push(uid, title=title, body=body[:140], url=url, kind=kind))
    return len(followers)


def notify_followers_soon(*args, **kwargs):
    try:
        asyncio.get_running_loop().create_task(notify_followers(*args, **kwargs))
    except RuntimeError:
        pass


# ---------- Staff Picks ----------
class StaffPicksReq(BaseModel):
    title: str = Field(default="Staff Picks", max_length=80)
    blurb: Optional[str] = Field(default=None, max_length=300)
    artwork_ids: List[str] = Field(default_factory=list)
    event_ids: List[str] = Field(default_factory=list)


@router.get("/staff-picks")
async def staff_picks():
    s = await db.settings.find_one({"id": "global"}) or {}
    sp = s.get("staff_picks") or {}
    art_ids, ev_ids = sp.get("artwork_ids", [])[:12], sp.get("event_ids", [])[:6]
    arts = {a["id"]: a for a in await db.artworks.find({"id": {"$in": art_ids}, "status": {"$in": ["live", "sold"]}}).to_list(20)}
    evs = {e["id"]: e for e in await db.events.find({"id": {"$in": ev_ids}, "cancelled": {"$ne": True}, "start_at": {"$gte": now_iso()}}).to_list(20)}
    artworks = []
    for i in art_ids:
        if i in arts:
            a = strip_mongo(arts[i]); artist = await db.users.find_one({"id": a["artist_id"]})
            a["artist"] = {"id": a["artist_id"], "name": (artist or {}).get("name")}
            artworks.append(a)
    return {"title": sp.get("title") or "Staff Picks", "blurb": sp.get("blurb"), "updated_at": sp.get("updated_at"),
            "artworks": artworks, "events": [strip_mongo(evs[i]) for i in ev_ids if i in evs]}


@router.put("/admin/staff-picks")
async def set_staff_picks(req: StaffPicksReq, user=Depends(require_role("admin"))):
    sp = {"title": req.title, "blurb": req.blurb, "artwork_ids": req.artwork_ids[:12], "event_ids": req.event_ids[:6],
          "updated_at": now_iso(), "updated_by": user["id"]}
    await db.settings.update_one({"id": "global"}, {"$set": {"staff_picks": sp}}, upsert=True)
    return sp


# ---------- Calendar feed (webcal) ----------
@router.post("/calendar/token")
async def calendar_token(request: Request, user: dict = Depends(get_current_user)):
    tok = user.get("calendar_token")
    if not tok:
        tok = secrets.token_urlsafe(24)
        await db.users.update_one({"id": user["id"]}, {"$set": {"calendar_token": tok}})
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    base = os.environ.get("PUBLIC_API_URL") or (f"{proto}://{host}" if host else APP_URL)
    https_url = f"{base}/api/calendar/{tok}.ics"
    return {"token": tok, "url": https_url, "webcal_url": https_url.replace("https://", "webcal://").replace("http://", "webcal://"),
            "google_url": f"https://calendar.google.com/calendar/r?cid={https_url.replace('https://', 'webcal://')}"}


@router.delete("/calendar/token")
async def reset_calendar_token(user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$unset": {"calendar_token": ""}})
    return {"ok": True}


def _ics_dt(iso: str) -> str:
    from datetime import datetime as _dt, timezone as _tz
    return _dt.fromisoformat(iso.replace("Z", "+00:00")).astimezone(_tz.utc).strftime("%Y%m%dT%H%M%SZ")


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/calendar/{token}.ics")
async def calendar_feed(token: str):
    u = await db.users.find_one({"calendar_token": token})
    if not u:
        raise HTTPException(404, "Calendar not found")
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    since = (_dt.now(_tz.utc) - _td(days=30)).isoformat()
    rsvp_ids = {r["event_id"] for r in await db.event_rsvps.find({"user_id": u["id"]}, {"event_id": 1}).to_list(2000)}
    saved_ids = {s["event_id"] for s in await db.event_saves.find({"user_id": u["id"]}, {"event_id": 1}).to_list(2000)}
    evs = await db.events.find({"id": {"$in": list(rsvp_ids | saved_ids)}, "cancelled": {"$ne": True}, "start_at": {"$gte": since}}).sort("start_at", 1).to_list(500)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Art Core//Events//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:Art Core — {_esc(u['name'])}", "X-WR-TIMEZONE:UTC", "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H"]
    for e in evs:
        loc = e.get("location") or {}
        where = ", ".join(x for x in [e.get("venue"), loc.get("address"), loc.get("city")] if x)
        status = "Going" if e["id"] in rsvp_ids else "Saved"
        end = e.get("end_at") or (_dt.fromisoformat(e["start_at"]) + _td(hours=2)).isoformat()
        lines += ["BEGIN:VEVENT", f"UID:{e['id']}@artcorestudio.net", f"DTSTAMP:{_ics_dt(now_iso())}", f"DTSTART:{_ics_dt(e['start_at'])}", f"DTEND:{_ics_dt(end)}",
                  f"SUMMARY:{_esc(e['title'])} ({status})", f"DESCRIPTION:{_esc((e.get('description') or '')[:600])}\\n\\n{APP_URL}/events/{e['id']}",
                  f"LOCATION:{_esc(where)}", f"URL:{APP_URL}/events/{e['id']}", f"CATEGORIES:{_esc((e.get('category') or '').replace('_', ' ').title())}"]
        if loc.get("lat") is not None:
            lines.append(f"GEO:{loc['lat']};{loc['lng']}")
        lines += ["BEGIN:VALARM", "TRIGGER:-PT24H", "ACTION:DISPLAY", f"DESCRIPTION:Tomorrow: {_esc(e['title'])}", "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="artcore.ics"', "Cache-Control": "private, max-age=600"})
