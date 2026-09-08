"""Direct messaging with attachments (artwork, studio, image), read receipts, search, unread counts."""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _thread_key(a: str, b: str) -> str:
    return "::".join(sorted([a, b]))


ATTACHMENT_KINDS = {"artwork", "studio", "image", "commission", "auction", "offer", "order"}


class Attachment(BaseModel):
    kind: str  # artwork | studio | image | commission | auction | offer | order
    ref_id: Optional[str] = None
    url: Optional[str] = None
    label: Optional[str] = None


class SendReq(BaseModel):
    to_user_id: str
    text: str = Field(default="", max_length=2000)
    attachment: Optional[Attachment] = None


async def _enrich_attachment(att: Optional[dict]) -> Optional[dict]:
    if not att:
        return None
    kind = att.get("kind")
    ref_id = att.get("ref_id")
    if kind == "artwork" and ref_id:
        a = await db.artworks.find_one({"id": ref_id})
        if a:
            artist = await db.users.find_one({"id": a.get("artist_id")})
            return {"kind": "artwork", "ref_id": ref_id,
                    "title": a["title"], "price": a.get("price"),
                    "image": (a.get("images") or [None])[0],
                    "artist_name": artist["name"] if artist else None,
                    "status": a.get("status")}
    if kind == "studio" and ref_id:
        u = await db.users.find_one({"id": ref_id})
        if u:
            return {"kind": "studio", "ref_id": ref_id, "name": u["name"]}
    if kind == "commission" and ref_id:
        c = await db.commissions.find_one({"id": ref_id})
        if c:
            return {"kind": "commission", "ref_id": ref_id, "subject": c["subject"], "status": c.get("status")}
    if kind == "auction" and ref_id:
        a = await db.auctions.find_one({"id": ref_id})
        if a:
            art = await db.artworks.find_one({"id": a["artwork_id"]})
            return {"kind": "auction", "ref_id": ref_id,
                    "title": art["title"] if art else "Auction",
                    "current_bid": a.get("current_bid"), "status": a.get("status")}
    if kind == "offer" and ref_id:
        o = await db.offers.find_one({"id": ref_id})
        if o:
            return {"kind": "offer", "ref_id": ref_id, "amount": o.get("amount"), "status": o.get("status")}
    if kind == "order" and ref_id:
        o = await db.orders.find_one({"id": ref_id})
        if o:
            return {"kind": "order", "ref_id": ref_id, "total": o.get("total"),
                    "status": (o.get("fulfillment") or {}).get("status")}
    if kind == "image":
        return {"kind": "image", "url": att.get("url"), "label": att.get("label")}
    return att


async def deliver_dm(sender: dict, to_user_id: str, text: str, attachment: Optional[dict] = None, notify: bool = True) -> dict:
    """Insert a DM from `sender` to `to_user_id` with throttled notification + push. Reused by broadcasts."""
    target = await db.users.find_one({"id": to_user_id})
    if not target:
        raise HTTPException(404, "User not found")
    msg = {
        "id": new_id(),
        "thread_key": _thread_key(sender["id"], to_user_id),
        "from_id": sender["id"], "from_name": sender["name"],
        "to_id": to_user_id, "to_name": target["name"],
        "text": text,
        "attachment": attachment,
        "read": False,
        "delivered_at": now_iso(),
        "read_at": None,
        "created_at": now_iso(),
    }
    await db.messages.insert_one(msg)
    from realtime import publish_soon
    publish_soon(f"user:{to_user_id}", {"type": "dm", "from_id": sender["id"], "message_id": msg["id"]})
    publish_soon(f"user:{sender['id']}", {"type": "dm", "from_id": sender["id"], "to_id": to_user_id, "message_id": msg["id"]})
    if not notify:
        return msg
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    existing = await db.notifications.find_one({
        "user_id": to_user_id, "kind": "new_message",
        "from_user_id": sender["id"], "created_at": {"$gte": cutoff},
    })
    if not existing:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": to_user_id, "kind": "new_message",
            "from_user_id": sender["id"], "from_user_name": sender["name"],
            "message_id": msg["id"], "preview": (text or f"Shared {attachment['kind']}")[:120],
            "read": False, "created_at": now_iso(),
        })
        try:
            from push import send_push
            import asyncio as _a
            _a.create_task(send_push(
                to_user_id,
                title=f"New message from {sender['name']}",
                body=(text or f"Shared a {attachment['kind']}")[:140],
                url=f"/messages/{sender['id']}",
                kind="new_message",
            ))
        except Exception:
            pass
    return msg


@router.post("")
async def send_message(req: SendReq, me: dict = Depends(get_current_user)):
    if req.to_user_id == me["id"]:
        raise HTTPException(400, "Cannot message yourself")
    text = (req.text or "").strip()
    if not text and not req.attachment:
        raise HTTPException(400, "Message empty")
    attachment = None
    if req.attachment:
        if req.attachment.kind not in ATTACHMENT_KINDS:
            raise HTTPException(400, f"Unknown attachment kind: {req.attachment.kind}")
        attachment = req.attachment.model_dump()
    msg = await deliver_dm(me, req.to_user_id, text, attachment)
    out = strip_mongo(msg)
    out["attachment"] = await _enrich_attachment(out.get("attachment"))
    return out


@router.get("/threads")
async def list_threads(q: Optional[str] = None, me: dict = Depends(get_current_user)):
    """List conversations with last message + unread count. If q, filter by other user name or last message."""
    cursor = db.messages.find({"$or": [{"from_id": me["id"]}, {"to_id": me["id"]}]}).sort("created_at", -1)
    all_msgs = [strip_mongo(m) for m in await cursor.to_list(2000)]
    threads: Dict[str, Any] = {}
    for m in all_msgs:
        k = m["thread_key"]
        if k in threads:
            continue
        other_id = m["to_id"] if m["from_id"] == me["id"] else m["from_id"]
        other_name = m["to_name"] if m["from_id"] == me["id"] else m["from_name"]
        unread = await db.messages.count_documents({"thread_key": k, "to_id": me["id"], "read": False})
        preview = m.get("text") or ""
        if not preview and m.get("attachment"):
            preview = f"[{m['attachment'].get('kind', 'attachment')}]"
        threads[k] = {
            "thread_key": k,
            "other_user_id": other_id,
            "other_user_name": other_name,
            "last_message": preview[:140],
            "last_at": m["created_at"],
            "last_from_me": m["from_id"] == me["id"],
            "last_read": bool(m.get("read")) if m["from_id"] == me["id"] else True,
            "unread": unread,
        }
    result = list(threads.values())
    if q:
        ql = q.lower().strip()
        result = [t for t in result if ql in t["other_user_name"].lower() or ql in t["last_message"].lower()]
    return result


@router.get("/thread/{user_id}")
async def get_thread(user_id: str, me: dict = Depends(get_current_user)):
    k = _thread_key(me["id"], user_id)
    cursor = db.messages.find({"thread_key": k}).sort("created_at", 1)
    raw = [strip_mongo(m) for m in await cursor.to_list(1000)]
    now = now_iso()
    # mark incoming as read (bulk)
    await db.messages.update_many(
        {"thread_key": k, "to_id": me["id"], "read": False},
        {"$set": {"read": True, "read_at": now}},
    )
    # Refresh + enrich attachments
    msgs = []
    for m in raw:
        if m["to_id"] == me["id"] and not m.get("read"):
            m["read"] = True
            m["read_at"] = now
        m["attachment"] = await _enrich_attachment(m.get("attachment"))
        msgs.append(m)
    other = await db.users.find_one({"id": user_id})
    return {
        "other": {"id": other["id"], "name": other["name"], "role": other["role"], "bio": other.get("bio")} if other else None,
        "messages": msgs,
        "other_typing": await _other_typing(me["id"], user_id),
    }


@router.post("/thread/{user_id}/read")
async def mark_thread_read(user_id: str, me: dict = Depends(get_current_user)):
    k = _thread_key(me["id"], user_id)
    now = now_iso()
    r = await db.messages.update_many({"thread_key": k, "to_id": me["id"], "read": False}, {"$set": {"read": True, "read_at": now}})
    return {"marked_read": r.modified_count}


@router.get("/unread-count")
async def unread_count(me: dict = Depends(get_current_user)):
    n = await db.messages.count_documents({"to_id": me["id"], "read": False})
    return {"count": n}


# ---------- Typing indicators ----------
@router.post("/thread/{user_id}/typing")
async def signal_typing(user_id: str, me: dict = Depends(get_current_user)):
    """Mark that `me` is typing to user_id — expires ~5s later."""
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(timezone.utc) + timedelta(seconds=6)).isoformat()
    await db.typing.update_one(
        {"from_id": me["id"], "to_id": user_id},
        {"$set": {"from_id": me["id"], "to_id": user_id, "expires_at": expires}},
        upsert=True,
    )
    from realtime import publish_soon
    publish_soon(f"user:{user_id}", {"type": "typing", "from_id": me["id"]})
    return {"ok": True}


async def _other_typing(me_id: str, other_id: str) -> bool:
    doc = await db.typing.find_one({"from_id": other_id, "to_id": me_id})
    if not doc:
        return False
    return doc["expires_at"] > now_iso()


# ---------- Reactions ----------
ALLOWED_REACTIONS = {"heart", "fire", "mind_blown", "wow", "clap", "eye"}


class ReactReq(BaseModel):
    emoji: str


@router.post("/{message_id}/react")
async def react(message_id: str, req: ReactReq, me: dict = Depends(get_current_user)):
    if req.emoji not in ALLOWED_REACTIONS:
        raise HTTPException(400, f"Emoji not allowed")
    m = await db.messages.find_one({"id": message_id})
    if not m:
        raise HTTPException(404, "Not found")
    if me["id"] not in (m["from_id"], m["to_id"]):
        raise HTTPException(403, "Not your thread")
    reactions = m.get("reactions") or []
    existing = next((r for r in reactions if r["user_id"] == me["id"] and r["emoji"] == req.emoji), None)
    if existing:
        reactions = [r for r in reactions if not (r["user_id"] == me["id"] and r["emoji"] == req.emoji)]
    else:
        # remove any prior emoji from this user first (one reaction per user per message)
        reactions = [r for r in reactions if r["user_id"] != me["id"]]
        reactions.append({"user_id": me["id"], "user_name": me["name"], "emoji": req.emoji, "at": now_iso()})
    await db.messages.update_one({"id": message_id}, {"$set": {"reactions": reactions}})
    return {"reactions": reactions}


@router.get("/search")
async def search_messages(q: str, me: dict = Depends(get_current_user)):
    """Full-text style search across the user's messages."""
    q = (q or "").strip()
    if not q:
        return []
    import re
    rx = re.compile(re.escape(q), re.IGNORECASE)
    cursor = db.messages.find({
        "$and": [
            {"$or": [{"from_id": me["id"]}, {"to_id": me["id"]}]},
            {"text": {"$regex": rx}},
        ]
    }).sort("created_at", -1).limit(50)
    return [strip_mongo(m) for m in await cursor.to_list(50)]
