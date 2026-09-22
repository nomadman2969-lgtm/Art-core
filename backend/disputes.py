"""Order disputes — buyer opens, admin resolves (refund full/partial or reject)."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, require_role

router = APIRouter(prefix="/api", tags=["disputes"])
REASONS = ["damaged", "not_received", "not_as_described", "other"]


class DisputeCreate(BaseModel):
    reason: str
    description: str = Field(min_length=10, max_length=3000)
    images: List[str] = Field(default_factory=list)

    @field_validator("images")
    @classmethod
    def _imgs(cls, v):
        bad = [p for p in v if p.startswith("http") or ".." in p]
        if bad:
            raise ValueError("images must be storage paths from /api/upload/image")
        return v[:6]

    @field_validator("reason")
    @classmethod
    def _r(cls, v):
        if v not in REASONS:
            raise ValueError(f"reason must be one of {REASONS}")
        return v


class ResolveReq(BaseModel):
    action: str  # refund_full | refund_partial | reject
    amount: Optional[float] = Field(default=None, gt=0)
    note: Optional[str] = Field(default=None, max_length=1000)


async def _enrich(d: dict) -> dict:
    d = strip_mongo(d)
    from artworks import sign_file_url
    d["image_urls"] = [sign_file_url(p) for p in d.get("images") or []]
    o = await db.orders.find_one({"id": d["order_id"]})
    if o:
        d["order"] = {"id": o["id"], "total": o.get("total"), "created_at": o.get("created_at"),
                      "refunded": bool(o.get("refunded")), "refund_amount": o.get("refund_amount")}
        first = (o.get("items") or [{}])[0]
        art = await db.artworks.find_one({"id": first.get("artwork_id")}) if first.get("artwork_id") else None
        if art:
            d["artwork"] = {"id": art["id"], "title": art["title"], "images": (art.get("images") or [])[:1]}
    buyer = await db.users.find_one({"id": d["buyer_id"]})
    if buyer:
        d["buyer"] = {"id": buyer["id"], "name": buyer["name"], "email": buyer.get("email")}
    seller = await db.users.find_one({"id": d.get("seller_id")}) if d.get("seller_id") else None
    if seller:
        d["seller"] = {"id": seller["id"], "name": seller["name"]}
    return d


async def _notify(user_id: str, kind: str, **extra):
    await db.notifications.insert_one({"id": new_id(), "user_id": user_id, "kind": kind, "read": False, "created_at": now_iso(), **extra})


@router.post("/orders/{oid}/dispute")
async def open_dispute(oid: str, req: DisputeCreate, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Order not found")
    if o.get("buyer_id") != user["id"]:
        raise HTTPException(403, "Only the buyer can open a dispute")
    if o.get("refunded"):
        raise HTTPException(400, "Order already refunded")
    if await db.disputes.find_one({"order_id": oid, "status": {"$in": ["open", "under_review"]}}):
        raise HTTPException(400, "A dispute is already open for this order")
    seller_id = (o.get("artist_payouts") or [{}])[0].get("artist_id")
    d = {
        "id": new_id(), "order_id": oid, "buyer_id": user["id"], "seller_id": seller_id,
        "reason": req.reason, "description": req.description, "images": req.images[:6],
        "status": "open", "resolution": None, "refund_amount": None, "admin_note": None,
        "history": [{"kind": "opened", "by": user["id"], "at": now_iso()}],
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.disputes.insert_one(d)
    from artworks import mark_private
    await mark_private(d["images"], {"kind": "order", "order_id": oid})
    from payouts import freeze_payouts
    await db.orders.update_one({"id": oid}, {"$set": {"dispute_status": "open", "dispute_id": d["id"], "artist_payouts": freeze_payouts(o, "disputed")}})
    if seller_id:
        await _notify(seller_id, "dispute_opened", dispute_id=d["id"], order_id=oid, reason=req.reason)
    async for admin in db.users.find({"role": "admin"}):
        await _notify(admin["id"], "dispute_opened", dispute_id=d["id"], order_id=oid, reason=req.reason, from_user_name=user["name"])
    return await _enrich(d)


@router.get("/orders/{oid}/dispute")
async def get_order_dispute(oid: str, user: dict = Depends(get_current_user)):
    d = await db.disputes.find_one({"order_id": oid}, sort=[("created_at", -1)])
    if not d:
        return None
    if user["id"] not in (d["buyer_id"], d.get("seller_id")) and user.get("role") != "admin":
        raise HTTPException(403, "Not yours")
    return await _enrich(d)


@router.get("/disputes/mine")
async def my_disputes(user: dict = Depends(get_current_user)):
    cursor = db.disputes.find({"$or": [{"buyer_id": user["id"]}, {"seller_id": user["id"]}]}).sort("created_at", -1).limit(100)
    return [await _enrich(d) for d in await cursor.to_list(100)]


@router.get("/admin/disputes")
async def admin_list(status: Optional[str] = None, user=Depends(require_role("admin"))):
    q = {"status": status} if status else {}
    cursor = db.disputes.find(q).sort("created_at", -1).limit(200)
    return [await _enrich(d) for d in await cursor.to_list(200)]


@router.post("/admin/disputes/{did}/resolve")
async def resolve(did: str, req: ResolveReq, user=Depends(require_role("admin"))):
    d = await db.disputes.find_one({"id": did})
    if not d:
        raise HTTPException(404, "Dispute not found")
    if d["status"] not in ("open", "under_review"):
        raise HTTPException(400, "Already resolved")
    if req.action not in ("refund_full", "refund_partial", "reject"):
        raise HTTPException(400, "Invalid action")
    refunded = 0.0
    if req.action != "reject":
        from admin import refund_order, RefundReq
        amount = None if req.action == "refund_full" else req.amount
        if req.action == "refund_partial" and not amount:
            raise HTTPException(400, "amount required for partial refund")
        result = await refund_order(d["order_id"], RefundReq(amount=amount, reason=f"Dispute {did}: {req.note or d['reason']}", reverse_payouts=True), user)
        refunded = float(result.get("refunded") or 0)
    status = "refunded" if req.action != "reject" else "rejected"
    await db.disputes.update_one({"id": did}, {"$set": {
        "status": status, "resolution": req.action, "refund_amount": refunded or None, "admin_note": req.note,
        "resolved_by": user["id"], "resolved_at": now_iso(), "updated_at": now_iso(),
    }, "$push": {"history": {"kind": req.action, "by": user["id"], "amount": refunded or None, "note": req.note, "at": now_iso()}}})
    await db.orders.update_one({"id": d["order_id"]}, {"$set": {"dispute_status": status}})
    if req.action == "reject":
        from payouts import unfreeze_payouts
        o = await db.orders.find_one({"id": d["order_id"]})
        if o:
            upd = {"artist_payouts": await unfreeze_payouts(o)}
            if (o.get("fulfillment") or {}).get("status") in ("not_received", "carrier_delivered", "shipped"):
                upd.update({"fulfillment.status": "delivered", "fulfillment.delivered_at": now_iso(), "fulfillment.confirmed_how": "admin_dispute_rejected"})
            await db.orders.update_one({"id": o["id"]}, {"$set": upd})
    await _notify(d["buyer_id"], "dispute_resolved", dispute_id=did, order_id=d["order_id"], resolution=req.action, amount=refunded or None)
    if d.get("seller_id"):
        await _notify(d["seller_id"], "dispute_resolved", dispute_id=did, order_id=d["order_id"], resolution=req.action, amount=refunded or None)
    return await _enrich(await db.disputes.find_one({"id": did}))
