"""Admin tools: dispute safety valve (auto-resolve stale disputes) + full data export."""
import csv
import io
import json
import os
import zipfile
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from db import db, now_iso, strip_mongo
from auth import require_role

router = APIRouter(prefix="/api/admin", tags=["admin-tools"])
DEFAULT_AUTO_DAYS = 7
WARN_DAYS_BEFORE = 2
SENSITIVE_USER_FIELDS = {"password_hash", "twofa_secret", "recovery_codes", "trusted_devices", "email_otp", "email_otp_expires"}


async def _auto_days() -> int:
    s = await db.settings.find_one({"id": "global"}) or {}
    return int(s.get("dispute_auto_days") or DEFAULT_AUTO_DAYS)


def _decide(d: dict, order: dict) -> tuple[str, str]:
    """Evidence-based default when nobody reviews: carrier-confirmed delivery beats a bare 'not received'; otherwise buyer wins."""
    f = (order or {}).get("fulfillment") or {}
    src = str(f.get("carrier_delivered_source") or "")
    if d.get("reason") == "not_received" and (src.startswith("carrier") or src in ("seller", "admin")) and f.get("tracking"):
        return "reject", f"Auto-resolved after {DEFAULT_AUTO_DAYS}+ days without review: tracking {f.get('carrier')} {f.get('tracking')} shows delivered ({src})."
    return "refund_full", f"Auto-resolved after {DEFAULT_AUTO_DAYS}+ days without admin review — buyer protection default."


async def sweep_stale_disputes() -> dict:
    days = await _auto_days()
    now = datetime.now(timezone.utc)
    warn_cut = (now - timedelta(days=max(days - WARN_DAYS_BEFORE, 1))).isoformat()
    resolve_cut = (now - timedelta(days=days)).isoformat()
    warned = resolved = 0
    q = {"status": {"$in": ["open", "under_review"]}, "created_at": {"$lte": warn_cut}}
    for d in await db.disputes.find(q).to_list(200):
        if d["created_at"] <= resolve_cut:
            order = await db.orders.find_one({"id": d["order_id"]})
            action, note = _decide(d, order)
            from disputes import resolve, ResolveReq
            admin = await db.users.find_one({"role": "admin"}) or {"id": "system", "name": "Art Core"}
            try:
                await resolve(d["id"], ResolveReq(action=action, note=note), user=admin)
                await db.disputes.update_one({"id": d["id"]}, {"$set": {"auto_resolved": True, "auto_resolved_at": now_iso()}})
                resolved += 1
            except Exception as e:
                await db.disputes.update_one({"id": d["id"]}, {"$set": {"auto_resolve_error": str(e)[:200]}})
                if not d.get("auto_resolve_error"):
                    for adm in await db.users.find({"role": "admin"}).to_list(20):
                        await db.notifications.insert_one({"id": os.urandom(8).hex(), "user_id": adm["id"], "kind": "dispute_auto_failed", "dispute_id": d["id"], "order_id": d["order_id"],
                                                            "error": str(e)[:120], "read": False, "created_at": now_iso()})
        elif not d.get("auto_warned"):
            for admin in await db.users.find({"role": "admin"}).to_list(20):
                await db.notifications.insert_one({"id": os.urandom(8).hex(), "user_id": admin["id"], "kind": "dispute_auto_warning", "dispute_id": d["id"], "order_id": d["order_id"],
                                                    "reason": d.get("reason"), "auto_in_days": WARN_DAYS_BEFORE, "read": False, "created_at": now_iso()})
            await db.disputes.update_one({"id": d["id"]}, {"$set": {"auto_warned": True}})
            warned += 1
    return {"warned": warned, "resolved": resolved, "days": days}


@router.post("/disputes/sweep")
async def run_sweep(user=Depends(require_role("admin"))):
    return await sweep_stale_disputes()


def _scrub_user(u: dict) -> dict:
    return {k: v for k, v in strip_mongo(u).items() if k not in SENSITIVE_USER_FIELDS}


def _csv(rows: list, fields: list) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("'" + str(v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v) for k, v in r.items()})
    return buf.getvalue()


@router.get("/export.zip")
async def export_all(user=Depends(require_role("admin"))):
    """One-click backup: JSON of every business collection + CSV summaries. Secrets stripped."""
    collections = ["artworks", "orders", "payment_transactions", "disputes", "offers", "auctions", "bids", "commissions", "reviews",
                   "events", "event_rsvps", "event_waitlist", "follows", "studio_configs", "studio_posts", "messages", "reports", "waiver_grants", "settings"]
    users = [_scrub_user(u) for u in await db.users.find({}).to_list(100000)]
    dump = {"exported_at": now_iso(), "users": users}
    for c in collections:
        dump[c] = [strip_mongo(x) for x in await db[c].find({}).to_list(200000)]
    payouts = []
    for o in dump["orders"]:
        for p in o.get("artist_payouts") or []:
            payouts.append({"order_id": o["id"], "order_created_at": o.get("created_at"), "buyer_id": o.get("buyer_id"), **p})
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("artcore_export.json", json.dumps(dump, default=str, indent=1))
        z.writestr("users.csv", _csv(users, ["id", "email", "name", "role", "created_at", "founding_member", "founding_number", "stripe_connect_status", "twofa_enabled", "language"]))
        z.writestr("orders.csv", _csv([{**o, "items": len(o.get("items") or []), "fulfillment_status": (o.get("fulfillment") or {}).get("status"), "tracking": (o.get("fulfillment") or {}).get("tracking")} for o in dump["orders"]],
                                      ["id", "created_at", "buyer_id", "total", "processing_fee", "status", "refunded", "refund_amount", "dispute_status", "fulfillment_status", "tracking", "items"]))
        z.writestr("payouts.csv", _csv(payouts, ["order_id", "order_created_at", "buyer_id", "artist_id", "artwork_id", "gross", "net", "status", "release_at", "hold_reason", "stripe_transfer_id", "transferred_at"]))
        z.writestr("transactions.csv", _csv(dump["payment_transactions"], ["id", "created_at", "kind", "amount", "status", "user_id", "session_id", "payment_intent", "refunded"]))
        z.writestr("README.txt", "Art Core data export\n\nartcore_export.json — every business collection (password hashes, 2FA secrets and device tokens removed).\n*.csv — spreadsheet-friendly summaries. Cells starting with = + - @ are quote-prefixed to block formula injection.\n")
    zbuf.seek(0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    await db.admin_audit.insert_one({"kind": "export", "by": user["id"], "at": now_iso(), "users": len(users), "orders": len(dump["orders"])})
    return StreamingResponse(zbuf, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="artcore-export-{stamp}.zip"', "Cache-Control": "no-store"})
