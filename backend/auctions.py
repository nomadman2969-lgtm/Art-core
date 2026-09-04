"""Live auctions: create, bid, finalize with winner."""
from datetime import datetime, timezone, timedelta
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


async def _reassign_if_expired(auction_id: str):
    """If a winner's 48h payment window elapsed without payment, forfeit and pass to next bidder."""
    a = await db.auctions.find_one({"id": auction_id})
    if not a or a["status"] != "ended":
        return
    if a.get("paid"):
        return
    deadline = a.get("payment_deadline")
    if not deadline:
        return
    if _iso_now() < _parse(deadline):
        return
    # Winner forfeited — find next highest bidder not in the forfeited set
    forfeits = list(a.get("forfeits", []))
    if a.get("winner_id"):
        forfeits.append({"user_id": a["winner_id"], "amount": a.get("final_price"), "at": now_iso()})
        await db.notifications.insert_one({
            "id": new_id(), "user_id": a["winner_id"], "kind": "auction_forfeited",
            "auction_id": auction_id, "artwork_id": a["artwork_id"],
            "read": False, "created_at": now_iso(),
        })
    forfeited_users = {f["user_id"] for f in forfeits}
    # Find next best bid from a distinct user not in forfeited
    bids = await db.bids.find({"auction_id": auction_id}).sort("amount", -1).to_list(500)
    next_winner = None
    for b in bids:
        if b["user_id"] not in forfeited_users:
            next_winner = b
            break
    if next_winner:
        new_deadline = datetime.now(timezone.utc) + timedelta(hours=48)
        await db.auctions.update_one({"id": auction_id}, {"$set": {
            "winner_id": next_winner["user_id"],
            "final_price": next_winner["amount"],
            "current_bid": next_winner["amount"],
            "current_bidder_id": next_winner["user_id"],
            "current_bidder_name": next_winner["user_name"],
            "payment_deadline": new_deadline.isoformat(),
            "forfeits": forfeits,
            "ended_at": now_iso(),
        }})
        await db.notifications.insert_one({
            "id": new_id(), "user_id": next_winner["user_id"], "kind": "auction_won",
            "auction_id": auction_id, "artwork_id": a["artwork_id"],
            "amount": next_winner["amount"], "read": False, "created_at": now_iso(),
        })
        # unmark artwork sold since we're re-opening to a different winner
        await db.artworks.update_one({"id": a["artwork_id"]}, {"$set": {"status": "sold"}})
    else:
        # No more bidders — cancel
        await db.auctions.update_one({"id": auction_id}, {"$set": {
            "winner_id": None, "final_price": None,
            "payment_deadline": None, "forfeits": forfeits,
            "status": "cancelled",
        }})
        await db.artworks.update_one({"id": a["artwork_id"]}, {"$set": {"status": "live"}})
        await db.notifications.insert_one({
            "id": new_id(), "user_id": a["seller_id"], "kind": "auction_cancelled",
            "auction_id": auction_id, "artwork_id": a["artwork_id"],
            "read": False, "created_at": now_iso(),
        })


async def _process_proxies(auction_id: str):
    """eBay-style proxy bidding. The highest-ceiling proxy secures the lead at
    (second_highest_ceiling + 1), capped at their own max, using a SINGLE atomic bid.
    First proxy on an empty auction bids the start_price (or their max, whichever is lower)."""
    for _ in range(10):  # safety cap; usually converges immediately
        a = await db.auctions.find_one({"id": auction_id})
        if not a or a["status"] != "live":
            return
        current = float(a.get("current_bid") or 0)
        current_bidder = a.get("current_bidder_id")
        start_price = float(a["start_price"])
        proxies = await db.proxy_bids.find({
            "auction_id": auction_id, "active": True,
        }).sort("max_amount", -1).to_list(50)
        if not proxies:
            return
        top = proxies[0]
        top_max = float(top["max_amount"])
        # Ceilings of OTHER users' proxies (competitors)
        other_ceilings = [float(p["max_amount"]) for p in proxies if p["user_id"] != top["user_id"]]
        competitor_ceiling = max(other_ceilings) if other_ceilings else 0.0
        # If the current leader is NOT top's user, their manual/proxy bid IS a competitor
        # threat that top needs to beat.
        if current_bidder and current_bidder != top["user_id"]:
            competitor_ceiling = max(competitor_ceiling, current)

        # Decide the target bid.
        if top["user_id"] == current_bidder:
            # Already leading. Only raise if a real competitor could out-bid.
            if competitor_ceiling <= current:
                return
            target = min(top_max, competitor_ceiling + 1)
        else:
            # Top isn't leading — take over.
            floor = start_price if current == 0 else current + 1
            if competitor_ceiling > 0:
                target = min(top_max, max(competitor_ceiling + 1, floor))
            else:
                target = min(top_max, floor)
        if target <= current:
            return
        # Atomic CAS with end_at + status guard to prevent racing with finalize
        match_filter = {"id": auction_id, "status": "live", "end_at": {"$gt": _iso_now().isoformat()}}
        if a.get("current_bid") is None:
            match_filter["$or"] = [{"current_bid": None}, {"current_bid": {"$exists": False}}]
        else:
            match_filter["current_bid"] = a["current_bid"]
        result = await db.auctions.find_one_and_update(
            match_filter,
            {"$set": {"current_bid": target,
                      "current_bidder_id": top["user_id"],
                      "current_bidder_name": top["user_name"]},
             "$inc": {"bid_count": 1}},
            return_document=True,
        )
        if not result:
            continue  # re-read and retry
        bid = {
            "id": new_id(), "auction_id": auction_id,
            "user_id": top["user_id"], "user_name": top["user_name"],
            "amount": target, "auto": True, "created_at": now_iso(),
        }
        await db.bids.insert_one(bid)
        prev_bidder = current_bidder
        if prev_bidder and prev_bidder != top["user_id"]:
            await db.notifications.insert_one({
                "id": new_id(), "user_id": prev_bidder, "kind": "outbid",
                "auction_id": auction_id, "artwork_id": a["artwork_id"],
                "amount": target, "read": False, "created_at": now_iso(),
            })
        # Loop only if another proxy could still push us higher — usually no.


async def _notify_watchers_leader_change(auction_id: str, new_leader_id: str, amount: float, artwork_id: str):
    watchers = await db.watchers.find({"auction_id": auction_id}).to_list(1000)
    for w in watchers:
        if w["user_id"] == new_leader_id:
            continue  # they'll get their own notif
        await db.notifications.insert_one({
            "id": new_id(), "user_id": w["user_id"], "kind": "watched_auction_leader",
            "auction_id": auction_id, "artwork_id": artwork_id,
            "amount": amount, "read": False, "created_at": now_iso(),
        })


async def _check_ending_soon(auction_id: str):
    """Notify current bidder + watchers 1h before end. Fire once (dedup via marker doc)."""
    a = await db.auctions.find_one({"id": auction_id})
    if not a or a["status"] != "live":
        return
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    try:
        end = _parse(a["end_at"])
    except Exception:
        return
    delta = end - now
    if delta > timedelta(hours=1) or delta < timedelta(seconds=0):
        return
    if a.get("ending_soon_notified"):
        return
    await db.auctions.update_one({"id": auction_id}, {"$set": {"ending_soon_notified": True}})
    recipients = set()
    if a.get("current_bidder_id"):
        recipients.add(a["current_bidder_id"])
    watchers = await db.watchers.find({"auction_id": auction_id}).to_list(500)
    for w in watchers:
        recipients.add(w["user_id"])
    for uid in recipients:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": uid, "kind": "auction_ending",
            "auction_id": auction_id, "artwork_id": a["artwork_id"],
            "current_bid": a.get("current_bid"), "end_at": a["end_at"],
            "read": False, "created_at": now_iso(),
        })


async def _check_deadline_warning(auction_id: str):
    a = await db.auctions.find_one({"id": auction_id})
    if not a or a["status"] != "ended" or a.get("paid") or a.get("deadline_warned"):
        return
    dl = a.get("payment_deadline")
    if not dl:
        return
    try:
        dl_dt = _parse(dl)
    except Exception:
        return
    hrs_left = (dl_dt - _iso_now()).total_seconds() / 3600.0
    if 0 < hrs_left <= 6:
        # Notify winner + all watchers
        recipients = {a.get("winner_id")} if a.get("winner_id") else set()
        for w in await db.watchers.find({"auction_id": auction_id}).to_list(1000):
            recipients.add(w["user_id"])
        recipients.discard(None)
        for uid in recipients:
            await db.notifications.insert_one({
                "id": new_id(), "user_id": uid, "kind": "auction_deadline_soon",
                "auction_id": auction_id, "artwork_id": a["artwork_id"],
                "hours_left": round(hrs_left, 1),
                "read": False, "created_at": now_iso(),
            })
        await db.auctions.update_one({"id": auction_id}, {"$set": {"deadline_warned": True}})


async def _activate_if_due(auction_id: str):
    """Flip scheduled → live when start_at passed."""
    a = await db.auctions.find_one({"id": auction_id})
    if not a or a["status"] != "scheduled":
        return
    start = a.get("start_at")
    if not start:
        return
    try:
        if _iso_now() >= _parse(start):
            await db.auctions.update_one(
                {"id": auction_id, "status": "scheduled"},
                {"$set": {"status": "live", "started_at": now_iso()}},
            )
    except Exception:
        pass


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
    # auto-activate scheduled
    if a["status"] == "scheduled":
        await _activate_if_due(a["id"])
    # auto-finalize if end passed
    if a["status"] == "live" and _iso_now() >= _parse(a["end_at"]):
        await _finalize(a["id"])
    # check "ending soon" (within 1h) — fires once
    if a["status"] == "live":
        await _check_ending_soon(a["id"])
    # check payment deadline reassignment
    if a["status"] == "ended" and a.get("payment_deadline"):
        await _reassign_if_expired(a["id"])
        await _check_deadline_warning(a["id"])
    fresh = await db.auctions.find_one({"id": a["id"]})
    if fresh:
        a = strip_mongo(fresh)
        if art:
            a["artwork"] = {"id": art["id"], "title": art["title"], "images": art.get("images", []), "price": art.get("price"), "medium": art.get("medium")}
        if seller:
            a["seller"] = {"id": seller["id"], "name": seller["name"]}
    return a


async def _finalize(auction_id: str):
    a = await db.auctions.find_one({"id": auction_id})
    if not a or a["status"] != "live":
        return
    winner_id = a.get("current_bidder_id")
    winning_bid = a.get("current_bid", 0)
    reserve = a.get("reserve_price", 0) or 0
    won = winner_id and winning_bid >= reserve
    payment_deadline = None
    if won:
        payment_deadline = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    updates = {
        "status": "ended",
        "winner_id": winner_id if won else None,
        "final_price": winning_bid if won else None,
        "payment_deadline": payment_deadline,
        "ended_at": now_iso(),
    }
    await db.auctions.update_one({"id": auction_id}, {"$set": updates})
    if won:
        await db.artworks.update_one({"id": a["artwork_id"]}, {"$set": {"status": "sold"}})
        await db.notifications.insert_one({
            "id": new_id(), "user_id": winner_id, "kind": "auction_won",
            "auction_id": auction_id, "artwork_id": a["artwork_id"],
            "amount": winning_bid, "read": False, "created_at": now_iso(),
        })
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
    start_at: Optional[str] = None  # ISO — if provided, auction is scheduled and auto-activates at that time


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
    # Determine start & end
    if req.start_at:
        try:
            start_dt = _parse(req.start_at)
        except Exception:
            raise HTTPException(400, "Invalid start_at")
        if start_dt < _iso_now() - timedelta(minutes=1):
            raise HTTPException(400, "start_at must be in the future")
    else:
        start_dt = _iso_now()
    end_dt = start_dt + timedelta(minutes=req.duration_minutes)
    is_scheduled = start_dt > _iso_now() + timedelta(seconds=30)
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
        "start_at": start_dt.isoformat(),
        "started_at": None if is_scheduled else now_iso(),
        "end_at": end_dt.isoformat(),
        "status": "scheduled" if is_scheduled else "live",
        "winner_id": None,
        "final_price": None,
        "created_at": now_iso(),
    }
    await db.auctions.insert_one(doc)
    return await _enrich(doc)


@router.get("")
async def list_auctions(status: Optional[str] = "live", limit: int = 60):
    limit = max(1, min(limit, 200))
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
    # auto-activate if start time passed
    if a["status"] == "scheduled":
        await _activate_if_due(auction_id)
        a = await db.auctions.find_one({"id": auction_id})
    # auto-finalize if past end
    if a["status"] == "live" and _iso_now() >= _parse(a["end_at"]):
        await _finalize(auction_id)
        a = await db.auctions.find_one({"id": auction_id})
    if a["status"] != "live":
        raise HTTPException(400, "Auction not live")
    if a["seller_id"] == user["id"]:
        raise HTTPException(400, "Cannot bid on your own auction")
    start_price = float(a["start_price"])
    current_bid = float(a.get("current_bid") or 0)
    min_next = max(start_price, current_bid + 1)
    if req.amount < min_next:
        raise HTTPException(400, f"Bid must be at least {min_next}")

    # ATOMIC compare-and-swap: only update if current_bid hasn't changed since we read it.
    # This prevents two concurrent bids from both winning.
    # Filter matches both "no bids yet" (current_bid missing/None) and "current_bid == what we saw".
    match_filter = {
        "id": auction_id,
        "status": "live",
        "end_at": {"$gt": _iso_now().isoformat()},
    }
    if a.get("current_bid") is None:
        match_filter["$or"] = [{"current_bid": None}, {"current_bid": {"$exists": False}}]
    else:
        match_filter["current_bid"] = a["current_bid"]

    result = await db.auctions.find_one_and_update(
        match_filter,
        {"$set": {"current_bid": req.amount,
                  "current_bidder_id": user["id"],
                  "current_bidder_name": user["name"]},
         "$inc": {"bid_count": 1}},
        return_document=True,
    )
    if not result:
        # Someone else bid concurrently — re-read and reject with fresh min
        fresh = await db.auctions.find_one({"id": auction_id})
        fresh_current = float(fresh.get("current_bid") or 0) if fresh else 0
        raise HTTPException(409, f"Bid rejected — another bid landed first. Current bid is {fresh_current}.")

    bid = {
        "id": new_id(), "auction_id": auction_id,
        "user_id": user["id"], "user_name": user["name"],
        "amount": req.amount, "created_at": now_iso(),
    }
    await db.bids.insert_one(bid)
    prev_bidder = a.get("current_bidder_id")
    # outbid notification
    if prev_bidder and prev_bidder != user["id"]:
        await db.notifications.insert_one({
            "id": new_id(), "user_id": prev_bidder, "kind": "outbid",
            "auction_id": auction_id, "artwork_id": a["artwork_id"],
            "amount": req.amount, "read": False, "created_at": now_iso(),
        })
    # Trigger any proxy bids
    await _process_proxies(auction_id)
    # Notify watchers of leader change (throttle: only if leader != previous)
    fresh = await db.auctions.find_one({"id": auction_id})
    if fresh and fresh.get("current_bidder_id") and fresh["current_bidder_id"] != prev_bidder:
        await _notify_watchers_leader_change(auction_id, fresh["current_bidder_id"], fresh["current_bid"], a["artwork_id"])
    return strip_mongo(bid)


# ---------- Proxy bids ----------
class ProxyBidReq(BaseModel):
    max_amount: float = Field(gt=0)


@router.post("/{auction_id}/proxy-bid")
async def set_proxy_bid(auction_id: str, req: ProxyBidReq, user: dict = Depends(get_current_user)):
    a = await db.auctions.find_one({"id": auction_id})
    if not a:
        raise HTTPException(404, "Not found")
    if a["status"] != "live":
        raise HTTPException(400, "Auction not live")
    if a["seller_id"] == user["id"]:
        raise HTTPException(400, "Cannot bid on your own auction")
    if req.max_amount <= float(a.get("current_bid") or a["start_price"]):
        raise HTTPException(400, "Max must exceed current bid")
    await db.proxy_bids.update_one(
        {"auction_id": auction_id, "user_id": user["id"]},
        {"$set": {
            "auction_id": auction_id, "user_id": user["id"], "user_name": user["name"],
            "max_amount": req.max_amount, "active": True, "created_at": now_iso(),
        }},
        upsert=True,
    )
    # Always let the proxy engine settle — the new proxy may either bid immediately
    # or force the current leader's proxy to raise.
    prev_bidder = a.get("current_bidder_id")
    prev_bid = a.get("current_bid")
    await _process_proxies(auction_id)
    fresh = await db.auctions.find_one({"id": auction_id})
    if fresh and fresh.get("current_bidder_id") and fresh["current_bidder_id"] != prev_bidder:
        await _notify_watchers_leader_change(auction_id, fresh["current_bidder_id"], fresh["current_bid"], a["artwork_id"])
    return {"proxy_set": True, "max_amount": req.max_amount, "current_bid": fresh.get("current_bid"), "leading": fresh.get("current_bidder_id") == user["id"]}


@router.delete("/{auction_id}/proxy-bid")
async def cancel_proxy_bid(auction_id: str, user: dict = Depends(get_current_user)):
    r = await db.proxy_bids.update_one({"auction_id": auction_id, "user_id": user["id"], "active": True}, {"$set": {"active": False}})
    return {"cancelled": r.modified_count}


@router.get("/{auction_id}/proxy-bid/mine")
async def my_proxy(auction_id: str, user: dict = Depends(get_current_user)):
    p = await db.proxy_bids.find_one({"auction_id": auction_id, "user_id": user["id"], "active": True})
    if not p:
        return {"active": False}
    return {"active": True, "max_amount": p["max_amount"]}


# ---------- Watchers ----------
@router.post("/{auction_id}/watch")
async def watch(auction_id: str, user: dict = Depends(get_current_user)):
    a = await db.auctions.find_one({"id": auction_id})
    if not a:
        raise HTTPException(404, "Not found")
    await db.watchers.update_one(
        {"auction_id": auction_id, "user_id": user["id"]},
        {"$setOnInsert": {"auction_id": auction_id, "user_id": user["id"], "created_at": now_iso()}},
        upsert=True,
    )
    count = await db.watchers.count_documents({"auction_id": auction_id})
    return {"watching": True, "count": count}


@router.delete("/{auction_id}/watch")
async def unwatch(auction_id: str, user: dict = Depends(get_current_user)):
    await db.watchers.delete_many({"auction_id": auction_id, "user_id": user["id"]})
    count = await db.watchers.count_documents({"auction_id": auction_id})
    return {"watching": False, "count": count}


@router.get("/{auction_id}/watch")
async def watch_status(auction_id: str, user: dict = Depends(get_current_user)):
    w = await db.watchers.find_one({"auction_id": auction_id, "user_id": user["id"]})
    count = await db.watchers.count_documents({"auction_id": auction_id})
    return {"watching": bool(w), "count": count}


@router.get("/{auction_id}/bids")
async def get_bids(auction_id: str, limit: int = 50):
    cursor = db.bids.find({"auction_id": auction_id}).sort("created_at", -1).limit(limit)
    return [strip_mongo(b) for b in await cursor.to_list(limit)]
