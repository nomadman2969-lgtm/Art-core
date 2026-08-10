"""Live auctions: create, bid, finalize with winner."""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso, strip_mongo
from auth import get_current_user, get_optional_user, require_role

router = APIRouter(prefix="/api/auctions", tags=["auctions"])


def _iso_now():
    return datetime.now(timezone.utc)


def _parse(dt: str) -> datetime:
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


async def _enrich(a: dict) -> dict:
    a = strip_mongo(a)
    if not a:
        return a
    art = await db.artworks.find_one({"id": a["artwork_id"]})
    if art:
        a["artwork"] = {
            "id": art["id"], "title": art["title"], "images": art.get("images", []),
            "price": art.get("price"), "medium": art.get("medium"),
        }
    seller = await db.users.find_one({"id": a["seller_id"]})
    if seller:
        a["seller"] = {"id": seller["id"], "name": seller["name"]}
    # auto-finalize if end passed
    if a["status"] == "live" and _iso_now() >= _parse(a["end_at"]):
        await _finalize(a["id"])
        fresh = await db.auctions.find_one({"id": a["id"]})
        a["status"] = fresh["status"]
        a["winner_id"] = fresh.get("winner_id")
    return a


async def _finalize(auction_id: str):
    a = await db.auctions.find_one({"id": auction_id})
    if not a or a["status"] != "live":
        return
    winner_id = a.get("current_bidder_id")
    winning_bid = a.get("current_bid", 0)
    reserve = a.get("reserve_price", 0) or 0
    won = winner_id and winning_bid >= reserve
    updates = {
        "status": "ended",
        "winner_id": winner_id if won else None,
        "final_price": winning_bid if won else None,
        "ended_at": now_iso(),
    }
    await db.auctions.update_one({"id": auction_id}, {"$set": updates})
    if won:
        # mark artwork sold
        await db.artworks.update_one({"id": a["artwork_id"]}, {"$set": {"status": "sold"}})
        # winner notification (stored in generic notifications collection for future notification page)
        await db.notifications.insert_one({
            "id": new_id(), "user_id": winner_id, "kind": "auction_won",
            "auction_id": auction_id, "artwork_id": a["artwork_id"],
            "amount": winning_bid, "read": False, "created_at": now_iso(),
        })
        # seller notification
        await db.notifications.insert_one({
            "id": new_id(), "user_id": a["seller_id"], "kind": "auction_sold",
            "auction_id": auction_id, "artwork_id": a["artwork_id"],
            "amount": winning_bid, "read": False, "created_at": now_iso(),
        })


class AuctionCreate(BaseModel):
    artwork_id: str
    start_price: float = Field(gt=0)
    reserve_price: float = Field(ge=0, default=0)
    duration_minutes: int = Field(ge=5, le=60 * 24 * 30)


@router.post("")
async def create_auction(req: AuctionCreate, user: dict = Depends(require_role("artist", "admin"))):
    art = await db.artworks.find_one({"id": req.artwork_id})
    if not art:
        raise HTTPException(404, "Artwork not found")
    if art["artist_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not your artwork")
    if art["status"] != "live":
        raise HTTPException(400, "Artwork must be live before auctioning")
    existing = await db.auctions.find_one({"artwork_id": req.artwork_id, "status": {"$in": ["scheduled", "live"]}})
    if existing:
        raise HTTPException(400, "Auction already running")
    end = datetime.now(timezone.utc).timestamp() + req.duration_minutes * 60
    end_iso = datetime.fromtimestamp(end, tz=timezone.utc).isoformat()
    doc = {
        "id": new_id(),
        "artwork_id": req.artwork_id,
        "seller_id": art["artist_id"],
        "start_price": req.start_price,
        "reserve_price": req.reserve_price,
        "current_bid": None,
        "current_bidder_id": None,
        "current_bidder_name": None,
        "bid_count": 0,
        "started_at": now_iso(),
        "end_at": end_iso,
        "status": "live",
        "winner_id": None,
        "final_price": None,
        "created_at": now_iso(),
    }
    await db.auctions.insert_one(doc)
    return await _enrich(doc)


@router.get("")
async def list_auctions(status: Optional[str] = "live", limit: int = 60):
    q: dict = {}
    if status and status != "all":
        q["status"] = status
    cursor = db.auctions.find(q).sort("end_at", 1).limit(limit)
    docs = await cursor.to_list(limit)
    return [await _enrich(d) for d in docs]


@router.get("/mine")
async def my_auctions(user: dict = Depends(get_current_user)):
    seller = await db.auctions.find({"seller_id": user["id"]}).sort("created_at", -1).to_list(100)
    won = await db.auctions.find({"winner_id": user["id"]}).sort("ended_at", -1).to_list(100)
    return {
        "selling": [await _enrich(d) for d in seller],
        "won": [await _enrich(d) for d in won],
    }


@router.get("/{auction_id}")
async def get_auction(auction_id: str):
    a = await db.auctions.find_one({"id": auction_id})
    if not a:
        raise HTTPException(404, "Not found")
    return await _enrich(a)


class BidReq(BaseModel):
    amount: float = Field(gt=0)


@router.post("/{auction_id}/bid")
async def place_bid(auction_id: str, req: BidReq, user: dict = Depends(get_current_user)):
    a = await db.auctions.find_one({"id": auction_id})
    if not a:
        raise HTTPException(404, "Not found")
    # auto-finalize if past end
    if a["status"] == "live" and _iso_now() >= _parse(a["end_at"]):
        await _finalize(auction_id)
        a = await db.auctions.find_one({"id": auction_id})
    if a["status"] != "live":
        raise HTTPException(400, "Auction not live")
    if a["seller_id"] == user["id"]:
        raise HTTPException(400, "Cannot bid on your own auction")
    min_next = max(float(a["start_price"]), float(a.get("current_bid") or 0) + 1)
    if req.amount < min_next:
        raise HTTPException(400, f"Bid must be at least {min_next}")
    bid = {
        "id": new_id(), "auction_id": auction_id,
        "user_id": user["id"], "user_name": user["name"],
        "amount": req.amount, "created_at": now_iso(),
    }
    await db.bids.insert_one(bid)
    prev_bidder = a.get("current_bidder_id")
    await db.auctions.update_one(
        {"id": auction_id},
        {"$set": {"current_bid": req.amount, "current_bidder_id": user["id"], "current_bidder_name": user["name"]},
         "$inc": {"bid_count": 1}},
    )
    # outbid notification
    if prev_bidder and prev_bidder != user["id"]:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": prev_bidder, "kind": "outbid",
            "auction_id": auction_id, "artwork_id": a["artwork_id"],
            "amount": req.amount, "read": False, "created_at": now_iso(),
        })
    return strip_mongo(bid)


@router.get("/{auction_id}/bids")
async def get_bids(auction_id: str, limit: int = 50):
    cursor = db.bids.find({"auction_id": auction_id}).sort("created_at", -1).limit(limit)
    return [strip_mongo(b) for b in await cursor.to_list(limit)]
