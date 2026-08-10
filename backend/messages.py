"""Basic direct messaging."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _thread_key(a: str, b: str) -> str:
    return "::".join(sorted([a, b]))


class SendReq(BaseModel):
    to_user_id: str
    text: str = Field(min_length=1, max_length=2000)


@router.post("")
async def send_message(req: SendReq, me: dict = Depends(get_current_user)):
    if req.to_user_id == me["id"]:
        raise HTTPException(400, "Cannot message yourself")
    target = await db.users.find_one({"id": req.to_user_id})
    if not target:
        raise HTTPException(404, "User not found")
    msg = {
        "id": new_id(),
        "thread_key": _thread_key(me["id"], req.to_user_id),
        "from_id": me["id"], "from_name": me["name"],
        "to_id": req.to_user_id, "to_name": target["name"],
        "text": req.text,
        "read": False,
        "created_at": now_iso(),
    }
    await db.messages.insert_one(msg)
    return strip_mongo(msg)


@router.get("/threads")
async def list_threads(me: dict = Depends(get_current_user)):
    """Return the latest message per thread involving me."""
    cursor = db.messages.find({"$or": [{"from_id": me["id"]}, {"to_id": me["id"]}]}).sort("created_at", -1)
    all_msgs = [strip_mongo(m) for m in await cursor.to_list(2000)]
    threads = {}
    for m in all_msgs:
        k = m["thread_key"]
        if k in threads:
            continue
        other_id = m["to_id"] if m["from_id"] == me["id"] else m["from_id"]
        other_name = m["to_name"] if m["from_id"] == me["id"] else m["from_name"]
        unread = await db.messages.count_documents({"thread_key": k, "to_id": me["id"], "read": False})
        threads[k] = {
            "thread_key": k,
            "other_user_id": other_id,
            "other_user_name": other_name,
            "last_message": m["text"],
            "last_at": m["created_at"],
            "unread": unread,
        }
    return list(threads.values())


@router.get("/thread/{user_id}")
async def get_thread(user_id: str, me: dict = Depends(get_current_user)):
    k = _thread_key(me["id"], user_id)
    cursor = db.messages.find({"thread_key": k}).sort("created_at", 1)
    msgs = [strip_mongo(m) for m in await cursor.to_list(1000)]
    # mark incoming as read
    await db.messages.update_many({"thread_key": k, "to_id": me["id"], "read": False}, {"$set": {"read": True}})
    other = await db.users.find_one({"id": user_id})
    return {
        "other": {"id": other["id"], "name": other["name"], "role": other["role"]} if other else None,
        "messages": msgs,
    }


@router.get("/unread-count")
async def unread_count(me: dict = Depends(get_current_user)):
    n = await db.messages.count_documents({"to_id": me["id"], "read": False})
    return {"count": n}
