"""Buyer offers on live-priced artworks (make-an-offer flow)."""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user

router = APIRouter(prefix="/api/offers", tags=["offers"])

# Lifecycle:
# pending -> accepted | declined | countered | withdrawn | expired
# countered -> accepted (buyer accepts) | declined (buyer rejects counter) | withdrawn
# accepted -> paid (via /api/payments/offers/{id}/pay)


async def _enrich(o: dict) -> dict:
    o = strip_mongo(o)
    if not o:
        return o
    art = await db.artworks.find_one({"id": o["artwork_id"]})
    if art:
        o["artwork"] = {
            "id": art["id"], "title": art["title"],
            "images": art.get("images", [])[:2],
            "price": art.get("price"),
            "status": art.get("status"),
        }
    buyer = await db.users.find_one({"id": o["buyer_id"]})
    artist = await db.users.find_one({"id": o["artist_id"]})
    if buyer: o["buyer"] = {"id": buyer["id"], "name": buyer["name"]}
    if artist: o["artist"] = {"id": artist["id"], "name": artist["name"]}
    return o


class OfferCreate(BaseModel):
    artwork_id: str
    amount: float = Field(gt=0)
    message: Optional[str] = None


@router.post("")
async def create_offer(req: OfferCreate, me: dict = Depends(get_current_user)):
    art = await db.artworks.find_one({"id": req.artwork_id})
    if not art:
        raise HTTPException(404, "Artwork not found")
    if art["status"] != "live":
        raise HTTPException(400, "Artwork not available for offers")
    if art["artist_id"] == me["id"]:
        raise HTTPException(400, "Cannot offer on your own artwork")
    # Prevent duplicate open offer from same buyer
    existing = await db.offers.find_one({
        "artwork_id": req.artwork_id, "buyer_id": me["id"],
        "status": {"$in": ["pending", "countered"]},
    })
    if existing:
        raise HTTPException(400, "You already have an open offer on this piece")
    # Business rule: offer must be within 50–100% of list price
    price = float(art["price"])
    if req.amount < price * 0.5:
        raise HTTPException(400, f"Offer too low. Minimum is ${round(price * 0.5, 2)}")
    if req.amount > price:
        raise HTTPException(400, "Offer cannot exceed list price — buy it directly instead")
    o = {
        "id": new_id(),
        "artwork_id": req.artwork_id,
        "artist_id": art["artist_id"],
        "buyer_id": me["id"],
        "buyer_name": me["name"],
        "list_price": price,
        "amount": float(req.amount),
        "counter_amount": None,
        "message": req.message,
        "status": "pending",
        "history": [{"kind": "buyer_offer", "amount": float(req.amount), "at": now_iso(), "message": req.message}],
        "paid": False,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.offers.insert_one(o)
    await db.notifications.insert_one({
        "id": new_id(), "user_id": art["artist_id"], "kind": "offer_received",
        "offer_id": o["id"], "artwork_id": req.artwork_id, "amount": req.amount,
        "read": False, "created_at": now_iso(),
    })
    return await _enrich(o)


@router.get("/mine")
async def my_offers(as_role: str = "buyer", me: dict = Depends(get_current_user)):
    q = {"buyer_id": me["id"]} if as_role == "buyer" else {"artist_id": me["id"]}
    cursor = db.offers.find(q).sort("created_at", -1).limit(200)
    return [await _enrich(o) for o in await cursor.to_list(200)]


@router.get("/artwork/{aid}")
async def offers_for_artwork(aid: str, me: dict = Depends(get_current_user)):
    """Seller only — see all offers on their artwork."""
    art = await db.artworks.find_one({"id": aid})
    if not art:
        raise HTTPException(404, "Artwork not found")
    if art["artist_id"] != me["id"] and me["role"] != "admin":
        raise HTTPException(403, "Not yours")
    cursor = db.offers.find({"artwork_id": aid}).sort("created_at", -1).limit(200)
    return [await _enrich(o) for o in await cursor.to_list(200)]


@router.get("/{oid}")
async def get_offer(oid: str, me: dict = Depends(get_current_user)):
    o = await db.offers.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    if me["id"] not in (o["buyer_id"], o["artist_id"]) and me["role"] != "admin":
        raise HTTPException(403, "Not yours")
    return await _enrich(o)


class SellerResponse(BaseModel):
    action: str  # accept | decline | counter
    counter_amount: Optional[float] = None
    message: Optional[str] = None


@router.post("/{oid}/respond")
async def seller_respond(oid: str, req: SellerResponse, me: dict = Depends(get_current_user)):
    o = await db.offers.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    if o["artist_id"] != me["id"]:
        raise HTTPException(403, "Not the seller")
    if o["status"] not in ("pending",):
        raise HTTPException(400, "Offer no longer open to respond")
    # Verify artwork still live
    art = await db.artworks.find_one({"id": o["artwork_id"]})
    if not art or art["status"] != "live":
        raise HTTPException(400, "Artwork not available anymore")
    if req.action == "accept":
        new_status = "accepted"
        counter = None
        entry = {"kind": "seller_accepted", "at": now_iso()}
    elif req.action == "decline":
        new_status = "declined"
        counter = None
        entry = {"kind": "seller_declined", "at": now_iso(), "message": req.message}
    elif req.action == "counter":
        if req.counter_amount is None or req.counter_amount <= 0:
            raise HTTPException(400, "Counter amount required")
        if req.counter_amount > float(o["list_price"]):
            raise HTTPException(400, "Counter cannot exceed list price")
        if req.counter_amount <= float(o["amount"]):
            raise HTTPException(400, "Counter must exceed original offer")
        new_status = "countered"
        counter = float(req.counter_amount)
        entry = {"kind": "seller_countered", "amount": counter, "at": now_iso(), "message": req.message}
    else:
        raise HTTPException(400, "Invalid action")
    await db.offers.update_one(
        {"id": oid},
        {"$set": {"status": new_status, "counter_amount": counter, "updated_at": now_iso()},
         "$push": {"history": entry}},
    )
    await db.notifications.insert_one({
        "id": new_id(), "user_id": o["buyer_id"],
        "kind": f"offer_{req.action}",
        "offer_id": oid, "artwork_id": o["artwork_id"],
        "amount": counter if counter else o["amount"],
        "read": False, "created_at": now_iso(),
    })
    return await _enrich(await db.offers.find_one({"id": oid}))


class BuyerResponse(BaseModel):
    action: str  # accept_counter | decline_counter | withdraw


@router.post("/{oid}/buyer-action")
async def buyer_action(oid: str, req: BuyerResponse, me: dict = Depends(get_current_user)):
    o = await db.offers.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Not found")
    if o["buyer_id"] != me["id"]:
        raise HTTPException(403, "Not the buyer")
    if req.action == "withdraw":
        if o["status"] not in ("pending", "countered"):
            raise HTTPException(400, "Cannot withdraw at this stage")
        await db.offers.update_one({"id": oid},
            {"$set": {"status": "withdrawn", "updated_at": now_iso()},
             "$push": {"history": {"kind": "buyer_withdrew", "at": now_iso()}}})
        await db.notifications.insert_one({
            "id": new_id(), "user_id": o["artist_id"], "kind": "offer_withdrawn",
            "offer_id": oid, "artwork_id": o["artwork_id"],
            "read": False, "created_at": now_iso(),
        })
    elif req.action == "accept_counter":
        if o["status"] != "countered":
            raise HTTPException(400, "No counter to accept")
        # Ensure artwork still live
        art = await db.artworks.find_one({"id": o["artwork_id"]})
        if not art or art["status"] != "live":
            raise HTTPException(400, "Artwork not available anymore")
        await db.offers.update_one({"id": oid},
            {"$set": {"status": "accepted", "amount": o["counter_amount"], "updated_at": now_iso()},
             "$push": {"history": {"kind": "buyer_accepted_counter", "amount": o["counter_amount"], "at": now_iso()}}})
        await db.notifications.insert_one({
            "id": new_id(), "user_id": o["artist_id"], "kind": "offer_accepted_by_buyer",
            "offer_id": oid, "artwork_id": o["artwork_id"], "amount": o["counter_amount"],
            "read": False, "created_at": now_iso(),
        })
    elif req.action == "decline_counter":
        if o["status"] != "countered":
            raise HTTPException(400, "No counter to decline")
        await db.offers.update_one({"id": oid},
            {"$set": {"status": "declined", "updated_at": now_iso()},
             "$push": {"history": {"kind": "buyer_declined_counter", "at": now_iso()}}})
    else:
        raise HTTPException(400, "Invalid action")
    return await _enrich(await db.offers.find_one({"id": oid}))
