"""Founding-artist fee waiver: 0% Art Core commission for the first N days (or M sales) after signup."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso
from auth import get_current_user, require_role

router = APIRouter(prefix="/api/waiver", tags=["waiver"])
admin_router = APIRouter(prefix="/api/admin/waiver", tags=["admin"])

DEFAULTS = {"waiver_enabled": True, "waiver_days": 30, "waiver_max_sales": 5,
            "founding_enabled": True, "founding_rate": 4.0, "founding_cap": 500}


def _now():
    return datetime.now(timezone.utc)


def waiver_cfg(settings: dict) -> dict:
    return {k: settings.get(k, v) for k, v in DEFAULTS.items()}


def waiver_status(user: dict, settings: dict) -> dict:
    cfg = waiver_cfg(settings)
    until = user.get("fee_waiver_until")
    sales_left = user.get("fee_waiver_sales_left")
    if not cfg["waiver_enabled"] or not until:
        return {"active": False, "until": until, "sales_left": sales_left, "days_left": 0}
    try:
        until_dt = datetime.fromisoformat(until)
    except Exception:
        return {"active": False, "until": until, "sales_left": sales_left, "days_left": 0}
    days_left = max(0, (until_dt - _now()).days + (1 if (until_dt - _now()).seconds > 0 else 0))
    active = until_dt > _now() and (sales_left is None or sales_left > 0)
    return {"active": active, "until": until, "sales_left": sales_left, "days_left": days_left if active else 0,
            "max_sales": cfg["waiver_max_sales"], "waiver_days": cfg["waiver_days"]}


async def grant_waiver(user_id: str, email: str, settings: dict, days: Optional[int] = None, sales: Optional[int] = None, source: str = "signup") -> Optional[dict]:
    cfg = waiver_cfg(settings)
    if source == "signup":
        if not cfg["waiver_enabled"]:
            return None
        if await db.waiver_grants.find_one({"email": email.lower(), "source": "signup"}):
            return None  # re-registering with the same email doesn't restart the clock
    days = days or cfg["waiver_days"]
    sales = cfg["waiver_max_sales"] if sales is None else sales
    until = (_now() + timedelta(days=days)).isoformat()
    await db.users.update_one({"id": user_id}, {"$set": {"fee_waiver_until": until, "fee_waiver_sales_left": sales, "fee_waiver_granted_at": now_iso()},
                                                 "$unset": {"waiver_reminder_7d_sent": "", "waiver_reminder_1d_sent": ""}})
    await db.waiver_grants.insert_one({"id": new_id(), "user_id": user_id, "email": email.lower(), "days": days, "sales": sales, "source": source, "created_at": now_iso()})
    return {"until": until, "sales_left": sales}


def effective_rate(seller: Optional[dict], settings: dict) -> dict:
    """Seller's commission after founding lock (min of locked & global) and the 0% window."""
    out = {**settings}
    locked = (seller or {}).get("locked_commission_percent")
    if locked is not None:
        out["commission_percent"] = min(float(locked), float(settings["commission_percent"]))
        out["founding_locked"] = True
    if seller and waiver_status(seller, settings)["active"]:
        out["commission_percent"] = 0.0
        out["fee_waived"] = True
    elif seller and int(seller.get("fee_free_sales") or 0) > 0:
        out["commission_percent"] = 0.0
        out["fee_free_referral"] = True
    return out


async def settings_for_seller(seller_id: str, settings: dict) -> dict:
    """Settings copy with the seller's effective commission (founding lock / 0% window applied)."""
    seller = await db.users.find_one({"id": seller_id}) if seller_id else None
    return effective_rate(seller, settings)


async def founding_stats(settings: dict) -> dict:
    cfg = waiver_cfg(settings)
    taken = await db.users.count_documents({"founding_member": True})
    return {"founding_enabled": cfg["founding_enabled"], "founding_rate": cfg["founding_rate"], "founding_cap": cfg["founding_cap"],
            "founding_taken": taken, "founding_left": max(0, int(cfg["founding_cap"]) - taken)}


async def grant_founding(user_id: str, settings: dict, source: str = "signup") -> Optional[dict]:
    """Lock the founding rate for life on this artist if spots remain (or always, when granted by admin)."""
    cfg = waiver_cfg(settings)
    u = await db.users.find_one({"id": user_id})
    if not u or u.get("founding_member"):
        return None
    if source == "signup":
        if not cfg["founding_enabled"]:
            return None
        if await db.users.count_documents({"founding_member": True}) >= int(cfg["founding_cap"]):
            return None
    number = await db.users.count_documents({"founding_member": True}) + 1
    await db.users.update_one({"id": user_id}, {"$set": {"founding_member": True, "founding_number": number,
                                                          "locked_commission_percent": float(cfg["founding_rate"]), "founding_granted_at": now_iso(), "founding_source": source}})
    return {"founding_number": number, "locked_commission_percent": float(cfg["founding_rate"])}


async def consume_waiver_sale(seller_id: str) -> None:
    await db.users.update_one({"id": seller_id, "fee_waiver_sales_left": {"$gt": 0}}, {"$inc": {"fee_waiver_sales_left": -1}})


async def after_sale(seller_id: str, seller_settings: dict) -> None:
    """Consume whichever 0% credit was used and fire referral conversion on a seller's first sale."""
    if seller_settings.get("fee_waived"):
        await consume_waiver_sale(seller_id)
    from referrals import consume_fee_free_sale, on_first_sale
    if seller_settings.get("fee_free_referral"):
        await consume_fee_free_sale(seller_id)
    await on_first_sale(seller_id)


@router.get("/me")
async def my_waiver(user: dict = Depends(get_current_user)):
    from payments import get_settings
    settings = await get_settings()
    eff = effective_rate(user, settings)
    return {**waiver_status(user, settings),
            "founding_member": bool(user.get("founding_member")), "founding_number": user.get("founding_number"),
            "locked_commission_percent": user.get("locked_commission_percent"),
            "effective_commission_percent": eff["commission_percent"], "standard_commission_percent": settings["commission_percent"]}


@admin_router.post("/founding/backfill")
async def founding_backfill(admin=Depends(require_role("admin"))):
    """Grant founding status to every existing artist who doesn't have it yet (ignores the cap)."""
    from payments import get_settings
    settings = await get_settings()
    granted = 0
    async for u in db.users.find({"role": "artist", "founding_member": {"$ne": True}}).sort("created_at", 1):
        if await grant_founding(u["id"], settings, source=f"backfill:{admin['id']}"):
            granted += 1
    return {"granted": granted, **(await founding_stats(settings))}


@admin_router.post("/founding/{user_id}")
async def founding_grant(user_id: str, admin=Depends(require_role("admin"))):
    from payments import get_settings
    settings = await get_settings()
    res = await grant_founding(user_id, settings, source=f"admin:{admin['id']}")
    if res is None:
        u = await db.users.find_one({"id": user_id})
        if not u:
            raise HTTPException(404, "User not found")
        raise HTTPException(400, "Already a founding member")
    return res


@admin_router.delete("/founding/{user_id}")
async def founding_revoke(user_id: str, admin=Depends(require_role("admin"))):
    await db.users.update_one({"id": user_id}, {"$unset": {"founding_member": "", "founding_number": "", "locked_commission_percent": "", "founding_granted_at": "", "founding_source": ""}})
    return {"ok": True}


class GrantReq(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    sales: Optional[int] = Field(default=None, ge=0, le=1000)


@admin_router.post("/{user_id}")
async def admin_grant(user_id: str, req: GrantReq, admin=Depends(require_role("admin"))):
    from payments import get_settings
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(404, "User not found")
    settings = await get_settings()
    cur = waiver_status(u, settings)
    base = datetime.fromisoformat(u["fee_waiver_until"]) if cur["active"] else _now()
    until = (base + timedelta(days=req.days)).isoformat()
    sales = settings.get("waiver_max_sales", 5) if req.sales is None else req.sales
    await db.users.update_one({"id": user_id}, {"$set": {"fee_waiver_until": until, "fee_waiver_sales_left": sales},
                                                 "$unset": {"waiver_reminder_7d_sent": "", "waiver_reminder_1d_sent": ""}})
    await db.waiver_grants.insert_one({"id": new_id(), "user_id": user_id, "email": u["email"], "days": req.days, "sales": sales, "source": f"admin:{admin['id']}", "created_at": now_iso()})
    fresh = await db.users.find_one({"id": user_id})
    return waiver_status(fresh, settings)


@admin_router.delete("/{user_id}")
async def admin_revoke(user_id: str, admin=Depends(require_role("admin"))):
    await db.users.update_one({"id": user_id}, {"$unset": {"fee_waiver_until": "", "fee_waiver_sales_left": ""}})
    return {"ok": True}


async def check_waiver_reminders():
    """Email artists 7 days and 1 day before their 0% window ends. Idempotent via user markers."""
    from payments import get_settings
    settings = await get_settings()
    if not waiver_cfg(settings)["waiver_enabled"]:
        return
    now = _now()
    horizon = (now + timedelta(days=7, hours=1)).isoformat()
    users = await db.users.find({"fee_waiver_until": {"$gt": now.isoformat(), "$lte": horizon}}).to_list(2000)
    for u in users:
        st = waiver_status(u, settings)
        if not st["active"]:
            continue
        left = datetime.fromisoformat(u["fee_waiver_until"]) - now
        if left <= timedelta(days=1) and not u.get("waiver_reminder_1d_sent"):
            await _send_waiver_reminder(u, settings, "1d", "ends tomorrow")
        elif left <= timedelta(days=7) and not u.get("waiver_reminder_7d_sent"):
            await _send_waiver_reminder(u, settings, "7d", "ends in a week")


async def _send_waiver_reminder(u: dict, settings: dict, marker: str, tail: str):
    await db.users.update_one({"id": u["id"]}, {"$set": {f"waiver_reminder_{marker}_sent": now_iso()}})
    await db.notifications.insert_one({"id": new_id(), "user_id": u["id"], "kind": "waiver_ending", "tail": tail,
                                       "commission_percent": settings["commission_percent"], "read": False, "created_at": now_iso()})
    try:
        from emails import send_email, waiver_ending_html
        import asyncio
        asyncio.create_task(send_email(u["email"], f"Your 0% founding window {tail}", waiver_ending_html(u.get("name") or "there", tail, float(settings["commission_percent"]))))
    except Exception:
        pass
