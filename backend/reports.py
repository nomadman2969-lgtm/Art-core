"""Content reports — anyone can flag artwork/post/user/event; admins moderate."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, require_role

router = APIRouter(prefix="/api", tags=["reports"])
TARGETS = {"artwork": "artworks", "post": "studio_posts", "user": "users", "event": "events"}
REASONS = ["spam", "stolen_art", "inappropriate", "harassment", "scam", "copyright", "other"]
ACTIONS = ["dismiss", "remove_content", "warn_user", "suspend_user"]


class ReportCreate(BaseModel):
    target_type: str
    target_id: str
    reason: str
    details: Optional[str] = Field(default=None, max_length=1500)

    @field_validator("target_type")
    @classmethod
    def _t(cls, v):
        if v not in TARGETS:
            raise ValueError(f"target_type must be one of {list(TARGETS)}")
        return v

    @field_validator("reason")
    @classmethod
    def _r(cls, v):
        if v not in REASONS:
            raise ValueError(f"reason must be one of {REASONS}")
        return v


class ResolveReq(BaseModel):
    action: str
    note: Optional[str] = Field(default=None, max_length=1000)


async def _owner_id(target_type: str, doc: dict) -> Optional[str]:
    return {"artwork": doc.get("artist_id"), "post": doc.get("artist_id"), "user": doc.get("id"), "event": doc.get("host_id")}[target_type]


async def _enrich(r: dict) -> dict:
    r = strip_mongo(r)
    doc = await db[TARGETS[r["target_type"]]].find_one({"id": r["target_id"]})
    if doc:
        r["target"] = {
            "title": doc.get("title") or doc.get("name") or (doc.get("text") or "")[:80],
            "image": (doc.get("images") or [doc.get("image") or doc.get("cover_image") or doc.get("avatar")])[0],
            "status": doc.get("status"), "removed": bool(doc.get("removed")) or doc.get("status") == "removed",
        }
        owner = await db.users.find_one({"id": await _owner_id(r["target_type"], doc)})
        if owner:
            r["owner"] = {"id": owner["id"], "name": owner["name"], "suspended": owner.get("approved") is False}
    reporter = await db.users.find_one({"id": r["reporter_id"]})
    if reporter:
        r["reporter"] = {"id": reporter["id"], "name": reporter["name"]}
    return r


@router.post("/reports")
async def create_report(req: ReportCreate, user: dict = Depends(get_current_user)):
    doc = await db[TARGETS[req.target_type]].find_one({"id": req.target_id})
    if not doc:
        raise HTTPException(404, "Target not found")
    if await _owner_id(req.target_type, doc) == user["id"]:
        raise HTTPException(400, "You can't report your own content")
    if await db.reports.find_one({"reporter_id": user["id"], "target_type": req.target_type, "target_id": req.target_id, "status": "open"}):
        raise HTTPException(400, "You already reported this — our team is on it")
    r = {"id": new_id(), "reporter_id": user["id"], "target_type": req.target_type, "target_id": req.target_id,
         "reason": req.reason, "details": req.details, "status": "open", "action": None, "note": None,
         "created_at": now_iso(), "updated_at": now_iso()}
    await db.reports.insert_one(r)
    open_count = await db.reports.count_documents({"target_type": req.target_type, "target_id": req.target_id, "status": "open"})
    async for admin in db.users.find({"role": "admin"}):
        await db.notifications.insert_one({"id": new_id(), "user_id": admin["id"], "kind": "report_opened", "report_id": r["id"],
                                           "target_type": req.target_type, "reason": req.reason, "open_count": open_count,
                                           "from_user_name": user["name"], "read": False, "created_at": now_iso()})
    return {"ok": True, "id": r["id"]}


@router.get("/admin/reports")
async def list_reports(status: Optional[str] = None, user=Depends(require_role("admin"))):
    q = {"status": status} if status else {}
    items = [await _enrich(r) for r in await db.reports.find(q).sort("created_at", -1).limit(300).to_list(300)]
    return items


@router.get("/admin/reports/stats")
async def report_stats(user=Depends(require_role("admin"))):
    return {"open": await db.reports.count_documents({"status": "open"}), "total": await db.reports.count_documents({})}


@router.post("/admin/reports/{rid}/resolve")
async def resolve(rid: str, req: ResolveReq, user=Depends(require_role("admin"))):
    r = await db.reports.find_one({"id": rid})
    if not r:
        raise HTTPException(404, "Report not found")
    if r["status"] != "open":
        raise HTTPException(400, "Already resolved")
    if req.action not in ACTIONS:
        raise HTTPException(400, f"action must be one of {ACTIONS}")
    coll = TARGETS[r["target_type"]]
    doc = await db[coll].find_one({"id": r["target_id"]})
    owner_id = await _owner_id(r["target_type"], doc) if doc else None

    if req.action == "remove_content" and doc:
        if r["target_type"] == "artwork":
            await db.artworks.update_one({"id": doc["id"]}, {"$set": {"status": "removed", "removed": True, "removed_at": now_iso()}})
        elif r["target_type"] == "post":
            await db.studio_posts.update_one({"id": doc["id"]}, {"$set": {"removed": True, "hidden": True, "removed_at": now_iso()}})
        elif r["target_type"] == "event":
            await db.events.update_one({"id": doc["id"]}, {"$set": {"cancelled": True, "removed": True, "removed_at": now_iso()}})
        elif r["target_type"] == "user":
            await db.users.update_one({"id": doc["id"]}, {"$set": {"approved": False, "suspended_at": now_iso()}})
    if req.action == "suspend_user" and owner_id:
        await db.users.update_one({"id": owner_id}, {"$set": {"approved": False, "suspended_at": now_iso()}})

    # resolve every open report on the same target together
    await db.reports.update_many({"target_type": r["target_type"], "target_id": r["target_id"], "status": "open"},
                                 {"$set": {"status": "resolved", "action": req.action, "note": req.note,
                                           "resolved_by": user["id"], "resolved_at": now_iso(), "updated_at": now_iso()}})
    for rep in await db.reports.find({"target_type": r["target_type"], "target_id": r["target_id"], "resolved_at": {"$exists": True}}).to_list(200):
        await db.notifications.insert_one({"id": new_id(), "user_id": rep["reporter_id"], "kind": "report_resolved", "report_id": rep["id"],
                                           "target_type": r["target_type"], "action": req.action, "read": False, "created_at": now_iso()})
    if owner_id and req.action in ("remove_content", "warn_user", "suspend_user"):
        await db.notifications.insert_one({"id": new_id(), "user_id": owner_id, "kind": "moderation_action", "target_type": r["target_type"],
                                           "target_id": r["target_id"], "action": req.action, "note": req.note, "read": False, "created_at": now_iso()})
    return await _enrich(await db.reports.find_one({"id": rid}))
