"""Commission requests: buyer → artist → progress → deliver → approve."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user

router = APIRouter(prefix="/api/commissions", tags=["commissions"])


async def _enrich(c: dict) -> dict:
    c = strip_mongo(c)
    if not c:
        return c
    buyer = await db.users.find_one({"id": c["buyer_id"]})
    artist = await db.users.find_one({"id": c["artist_id"]})
    if buyer:
        c["buyer"] = {"id": buyer["id"], "name": buyer["name"]}
    if artist:
        c["artist"] = {"id": artist["id"], "name": artist["name"]}
    return c


class FurnitureDetails(BaseModel):
    furniture_type: str = Field(min_length=2, max_length=40)
    dimensions: Optional[str] = Field(default=None, max_length=80)
    condition: Optional[str] = Field(default=None, max_length=40)
    handoff: str = Field(default="dropoff", pattern="^(dropoff|ship|pickup)$")
    city: Optional[str] = Field(default=None, max_length=80)


class CommissionCreate(BaseModel):
    artist_id: str
    subject: str
    style: Optional[str] = None
    size: Optional[str] = None
    budget: float = Field(gt=0)
    deadline: Optional[str] = None  # ISO date
    instructions: str
    reference_images: List[str] = Field(default_factory=list)  # storage paths
    kind: str = Field(default="art", pattern="^(art|flip)$")
    furniture: Optional[FurnitureDetails] = None


@router.get("/flip/artists")
async def flip_artists(limit: int = 24):
    """Artists with live/sold Upcycle work — the ones who take furniture flips."""
    rows = await db.artworks.aggregate([
        {"$match": {"section": "upcycle", "status": {"$in": ["live", "sold"]}}},
        {"$group": {"_id": "$artist_id", "pieces": {"$sum": 1}, "types": {"$addToSet": "$furniture_type"}, "sample": {"$first": "$images"}, "before": {"$first": "$before_image"}}},
        {"$sort": {"pieces": -1}}, {"$limit": limit},
    ]).to_list(limit)
    out = []
    for r in rows:
        u = await db.users.find_one({"id": r["_id"]})
        if not u:
            continue
        done = await db.commissions.count_documents({"artist_id": u["id"], "kind": "flip", "status": "approved"})
        loc = u.get("location") or {}
        out.append({
            "id": u["id"], "name": u["name"], "avatar": u.get("avatar"), "bio": (u.get("bio") or "")[:140],
            "city": loc.get("city") if isinstance(loc, dict) else None,
            "pieces": r["pieces"], "types": [t for t in r["types"] if t], "flips_done": done,
            "sample": (r.get("sample") or [None])[0], "before": r.get("before"),
        })
    return out


@router.post("")
async def create_commission(req: CommissionCreate, me: dict = Depends(get_current_user)):
    artist = await db.users.find_one({"id": req.artist_id, "role": "artist"})
    if not artist:
        raise HTTPException(404, "Artist not found")
    if req.artist_id == me["id"]:
        raise HTTPException(400, "Cannot commission yourself")
    if req.kind == "flip":
        if not req.furniture:
            raise HTTPException(400, "Tell the artist about the piece (type, size, hand-off)")
        if not req.reference_images:
            raise HTTPException(400, "Add at least one photo of the furniture")
    c = {
        "kind": req.kind,
        "furniture": req.furniture.model_dump() if req.furniture else None,
        "id": new_id(),
        "buyer_id": me["id"], "artist_id": req.artist_id,
        "subject": req.subject, "style": req.style, "size": req.size,
        "budget": req.budget, "deadline": req.deadline, "instructions": req.instructions,
        "reference_images": req.reference_images,
        "status": "pending",  # pending -> accepted/declined/counter -> in_progress -> delivered -> approved
        "counter_amount": None,
        "progress": [],
        "final_images": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.commissions.insert_one(c)
    await db.notifications.insert_one({
        "id": new_id(), "user_id": req.artist_id, "kind": "commission_request",
        "commission_id": c["id"], "read": False, "created_at": now_iso(),
    })
    return await _enrich(c)


@router.get("/mine")
async def my_commissions(as_role: str = "buyer", me: dict = Depends(get_current_user)):
    q = {"buyer_id": me["id"]} if as_role == "buyer" else {"artist_id": me["id"]}
    cursor = db.commissions.find(q).sort("created_at", -1).limit(100)
    return [await _enrich(c) for c in await cursor.to_list(100)]


@router.get("/{cid}")
async def get_commission(cid: str, me: dict = Depends(get_current_user)):
    c = await db.commissions.find_one({"id": cid})
    if not c:
        raise HTTPException(404, "Not found")
    if me["id"] not in (c["buyer_id"], c["artist_id"]) and me["role"] != "admin":
        raise HTTPException(403, "Not yours")
    return await _enrich(c)


# Public: completed commissions for an artist (proof of work rail)
public_router = APIRouter(prefix="/api", tags=["commissions-public"])


@public_router.get("/artists/{artist_id}/completed-commissions")
async def artist_completed(artist_id: str, limit: int = 12):
    from db import strip_mongo as _sm
    cursor = db.commissions.find({
        "artist_id": artist_id,
        "status": {"$in": ["approved", "paid"]},
        "final_images": {"$exists": True, "$ne": []},
    }).sort("updated_at", -1).limit(limit)
    out = []
    for c in await cursor.to_list(limit):
        c = _sm(c)
        out.append({
            "id": c["id"], "subject": c["subject"],
            "final_images": c.get("final_images", []),
            "budget": c.get("counter_amount") or c.get("budget"),
            "completed_at": c.get("updated_at"),
        })
    return out


class RespondReq(BaseModel):
    action: str  # accept | decline | counter
    counter_amount: Optional[float] = None
    message: Optional[str] = None
    sketch_image: Optional[str] = None  # storage path — flip quotes attach a concept sketch
    timeline_days: Optional[int] = Field(default=None, ge=1, le=365)


@router.post("/{cid}/respond")
async def respond(cid: str, req: RespondReq, me: dict = Depends(get_current_user)):
    c = await db.commissions.find_one({"id": cid})
    if not c or c["artist_id"] != me["id"]:
        raise HTTPException(404, "Not found")
    if c["status"] != "pending":
        raise HTTPException(400, "Already responded")
    if req.action == "accept":
        new_status = "in_progress"
        counter = None
    elif req.action == "decline":
        new_status = "declined"
        counter = None
    elif req.action == "counter":
        if req.counter_amount is None or req.counter_amount <= 0:
            raise HTTPException(400, "Counter amount required")
        new_status = "counter"
        counter = req.counter_amount
    else:
        raise HTTPException(400, "Invalid action")
    updates = {"status": new_status, "counter_amount": counter, "updated_at": now_iso()}
    if req.action == "counter":
        updates["quote"] = {"amount": counter, "sketch_image": req.sketch_image, "note": req.message, "timeline_days": req.timeline_days, "at": now_iso()}
    await db.commissions.update_one(
        {"id": cid},
        {"$set": updates,
         "$push": {"progress": {"kind": f"artist_{req.action}", "message": req.message, "image": req.sketch_image, "at": now_iso()}}},
    )
    await db.notifications.insert_one({
        "id": new_id(), "user_id": c["buyer_id"], "kind": f"commission_{req.action}",
        "commission_id": cid, "read": False, "created_at": now_iso(),
    })
    return await _enrich(await db.commissions.find_one({"id": cid}))


class BuyerActionReq(BaseModel):
    action: str  # accept_counter | cancel


@router.post("/{cid}/buyer-action")
async def buyer_action(cid: str, req: BuyerActionReq, me: dict = Depends(get_current_user)):
    c = await db.commissions.find_one({"id": cid})
    if not c or c["buyer_id"] != me["id"]:
        raise HTTPException(404, "Not found")
    if req.action == "accept_counter":
        if c["status"] != "counter":
            raise HTTPException(400, "No counter to accept")
        await db.commissions.update_one({"id": cid}, {"$set": {"status": "in_progress", "budget": c["counter_amount"], "updated_at": now_iso()}, "$push": {"progress": {"kind": "buyer_accepted_counter", "at": now_iso()}}})
    elif req.action == "cancel":
        if c["status"] in ("delivered", "approved"):
            raise HTTPException(400, "Cannot cancel completed")
        await db.commissions.update_one({"id": cid}, {"$set": {"status": "cancelled", "updated_at": now_iso()}})
    else:
        raise HTTPException(400, "Invalid action")
    return await _enrich(await db.commissions.find_one({"id": cid}))


class ProgressReq(BaseModel):
    message: str
    image: Optional[str] = None


@router.post("/{cid}/progress")
async def add_progress(cid: str, req: ProgressReq, me: dict = Depends(get_current_user)):
    c = await db.commissions.find_one({"id": cid})
    if not c or c["artist_id"] != me["id"]:
        raise HTTPException(404, "Not found")
    if c["status"] != "in_progress":
        raise HTTPException(400, "Not in progress")
    await db.commissions.update_one({"id": cid},
        {"$push": {"progress": {"kind": "artist_update", "message": req.message, "image": req.image, "at": now_iso()}},
         "$set": {"updated_at": now_iso()}})
    await db.notifications.insert_one({
        "id": new_id(), "user_id": c["buyer_id"], "kind": "commission_progress",
        "commission_id": cid, "read": False, "created_at": now_iso(),
    })
    return await _enrich(await db.commissions.find_one({"id": cid}))


class DeliverReq(BaseModel):
    message: Optional[str] = None
    final_images: List[str] = Field(default_factory=list)


@router.post("/{cid}/deliver")
async def deliver(cid: str, req: DeliverReq, me: dict = Depends(get_current_user)):
    c = await db.commissions.find_one({"id": cid})
    if not c or c["artist_id"] != me["id"]:
        raise HTTPException(404, "Not found")
    if c["status"] != "in_progress":
        raise HTTPException(400, "Not in progress")
    await db.commissions.update_one({"id": cid},
        {"$set": {"status": "delivered", "final_images": req.final_images, "updated_at": now_iso()},
         "$push": {"progress": {"kind": "artist_delivered", "message": req.message, "at": now_iso()}}})
    await db.notifications.insert_one({
        "id": new_id(), "user_id": c["buyer_id"], "kind": "commission_delivered",
        "commission_id": cid, "read": False, "created_at": now_iso(),
    })
    return await _enrich(await db.commissions.find_one({"id": cid}))


@router.post("/{cid}/approve")
async def approve(cid: str, me: dict = Depends(get_current_user)):
    c = await db.commissions.find_one({"id": cid})
    if not c or c["buyer_id"] != me["id"]:
        raise HTTPException(404, "Not found")
    if c["status"] != "delivered":
        raise HTTPException(400, "Not delivered")
    await db.commissions.update_one({"id": cid},
        {"$set": {"status": "approved", "updated_at": now_iso()},
         "$push": {"progress": {"kind": "buyer_approved", "at": now_iso()}}})
    await db.notifications.insert_one({
        "id": new_id(), "user_id": c["artist_id"], "kind": "commission_approved",
        "commission_id": cid, "read": False, "created_at": now_iso(),
    })
    return await _enrich(await db.commissions.find_one({"id": cid}))
