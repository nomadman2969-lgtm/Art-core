"""House of Monster — FastAPI backend."""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, Depends
from starlette.middleware.cors import CORSMiddleware

from db import db, now_iso, new_id
from auth import router as auth_router, hash_password, verify_password, get_optional_user
from twofa import router as twofa_router
from waiver import router as waiver_router, admin_router as waiver_admin_router, founding_stats
from pro import router as pro_router
from artworks import router as art_router
from payments import router as payments_router
from admin import router as admin_router, newsletter_router
from artist_dashboard import router as artist_router
from social import router as social_router
from messages import router as messages_router
from search import router as search_router
from auctions import router as auctions_router
from rankings import router as rankings_router
from commissions import router as commissions_router, public_router as commissions_public_router
from studio import router as studio_router, posts_router
from notifications import router as notifications_router
from orders import router as orders_router
from delivery import router as delivery_router
from tracking import router as tracking_router
from poster import router as poster_router
from admin_tools import router as admin_tools_router
from listing_assist import router as listing_assist_router
from referrals import router as referrals_router
from offers import router as offers_router
from realtime import router as realtime_router
from certificates import router as certificates_router
from disputes import router as disputes_router
from growth import router as growth_router
from reports import router as reports_router
from engage import router as engage_router
from connect import router as connect_router
from push import router as push_router
from events import router as events_router
from campus import router as campus_router, admin_router as campus_admin_router, ensure_seed as ensure_campus_seed
from storage import init_storage

app = FastAPI(title="Art Core")

app.include_router(auth_router)
app.include_router(twofa_router)
app.include_router(waiver_router)
app.include_router(waiver_admin_router)
app.include_router(pro_router)
app.include_router(art_router)
app.include_router(payments_router)
app.include_router(admin_router)
app.include_router(newsletter_router)
app.include_router(artist_router)
app.include_router(social_router)
app.include_router(messages_router)
app.include_router(search_router)
app.include_router(auctions_router)
app.include_router(rankings_router)
app.include_router(commissions_router)
app.include_router(commissions_public_router)
app.include_router(studio_router)
app.include_router(posts_router)
app.include_router(notifications_router)
app.include_router(delivery_router)
app.include_router(tracking_router)
app.include_router(poster_router)
app.include_router(admin_tools_router)
app.include_router(listing_assist_router)
app.include_router(referrals_router)
app.include_router(orders_router)
app.include_router(offers_router)
app.include_router(realtime_router)
app.include_router(certificates_router)
app.include_router(disputes_router)
app.include_router(growth_router)
app.include_router(reports_router)
app.include_router(engage_router)
app.include_router(connect_router)
app.include_router(push_router)
app.include_router(events_router)
app.include_router(campus_router)
app.include_router(campus_admin_router)


@app.get("/api/")
async def root():
    return {"app": "Art Core", "status": "ok"}


@app.get("/api/settings")
async def public_settings():
    s = await db.settings.find_one({"id": "global"})
    if not s:
        s = {"id": "global", "commission_percent": 4.0, "upload_fee": 5.0, "currency": "usd"}
    return {
        "commission_percent": s.get("commission_percent", 4.0),
        "upload_fee": s.get("upload_fee", 5.0),
        "currency": s.get("currency", "usd"),
        "processing_percent": s.get("processing_percent", 2.9),
        "processing_fixed": s.get("processing_fixed", 0.30),
        "seller_pays_processing": True,
        "waiver_enabled": s.get("waiver_enabled", True),
        "waiver_days": s.get("waiver_days", 30),
        "waiver_max_sales": s.get("waiver_max_sales", 5),
        "demo_login_enabled": s.get("demo_login_enabled", True),
        "stripe_mode": s.get("stripe_mode") or os.environ.get("STRIPE_MODE", "test"),
        "dispute_auto_days": s.get("dispute_auto_days", 7),
        **(await founding_stats(s)),
    }


@app.get("/api/settings/fee-preview")
async def fee_preview(gross: float, viewer=Depends(get_optional_user)):
    from payments import get_settings as _gs, split_amount
    from waiver import effective_rate
    settings = effective_rate(viewer, await _gs()) if viewer else await _gs()
    return {"gross": round(float(gross), 2), **split_amount(gross, settings), "commission_percent": settings["commission_percent"],
            "founding_locked": bool(settings.get("founding_locked")), "fee_waived": bool(settings.get("fee_waived"))}


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def _reminder_loop():
    import asyncio
    from events import check_event_reminders
    while True:
        try:
            await check_event_reminders()
        except Exception as e:
            logger.error(f"Reminder sweep failed: {e}")
        try:
            from payouts import release_due_payouts
            await release_due_payouts()
        except Exception as e:
            logger.error(f"Payout release sweep failed: {e}")
        try:
            from tracking import poll_active_trackers
            await poll_active_trackers()
        except Exception as e:
            logger.error(f"Tracking poll failed: {e}")
        try:
            from delivery import sweep_delivery_confirmations
            await sweep_delivery_confirmations()
        except Exception as e:
            logger.error(f"Delivery confirmation sweep failed: {e}")
        try:
            from admin_tools import sweep_stale_disputes
            await sweep_stale_disputes()
        except Exception as e:
            logger.error(f"Dispute safety-valve sweep failed: {e}")
        try:
            from waiver import check_waiver_reminders
            await check_waiver_reminders()
        except Exception as e:
            logger.error(f"Waiver sweep failed: {e}")
        await asyncio.sleep(600)


@app.on_event("startup")
async def startup():
    import asyncio
    from stripe_config import apply_stripe_keys
    try:
        await apply_stripe_keys()
    except Exception as e:
        logger.error(f"Stripe key apply failed: {e}")
    asyncio.get_running_loop().create_task(_reminder_loop())
    try:
        from pro import ensure_pro_catalog
        await asyncio.to_thread(ensure_pro_catalog)
    except Exception as e:
        logger.error(f"Pro catalog setup failed: {e}")
    # Init storage
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    try:
        await ensure_campus_seed()
    except Exception as e:
        logger.error(f"Campus seed failed: {e}")
    # Seed admin from env (password re-synced on every boot → rotate by changing ADMIN_PASSWORD)
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        admin = {
            "id": new_id(),
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Monster",
            "role": "admin",
            "bio": "Brooklyn-based abstract artist. Founder of Art Core. Lives with two cats and a lot of neon.",
            "cover_image": None,
            "avatar": None,
            "approved": True,
            "stripe_connect_status": "not_started",
            "created_at": now_iso(),
        }
        await db.users.insert_one(admin)
        logger.info("Seeded admin user")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password), "password_rotated_at": now_iso()}})
        logger.info("Rotated admin password from env")
    try:
        from ratelimit import ensure_indexes
        await ensure_indexes()
        from tracking import ensure_indexes as _ti
        await _ti()
    except Exception as e:
        logger.warning("rate limit indexes: %s", e)

    try:
        from seed_demo import refresh_demo_dates
        moved = await refresh_demo_dates()
        if moved:
            logger.info("Rolled %d demo events forward", moved)
    except Exception as e:  # noqa
        logger.warning("demo refresh skipped: %s", e)

    # Seed demo artist + demo collector (one-click login on /login)
    demo_accounts = [
        {
            "email": "demo.artist@artcorestudio.net",
            "password": os.environ["DEMO_ARTIST_PASSWORD"],
            "name": "Demo Artist",
            "role": "artist",
            "bio": "This is a demo artist account. Explore posting artworks, running auctions, and hosting events.",
        },
        {
            "email": "demo.collector@artcorestudio.net",
            "password": os.environ["DEMO_COLLECTOR_PASSWORD"],
            "name": "Demo Collector",
            "role": "buyer",
            "bio": "This is a demo buyer account. Explore browsing, offers, purchases, and RSVPing to events.",
        },
    ]
    _settings = await db.settings.find_one({"id": "global"}) or {}
    for d in (demo_accounts if _settings.get("demo_login_enabled", True) else []):
        existing_demo = await db.users.find_one({"email": d["email"]})
        if existing_demo:
            if not verify_password(d["password"], existing_demo["password_hash"]):
                await db.users.update_one({"email": d["email"]}, {"$set": {"password_hash": hash_password(d["password"]), "is_demo": True}})
            continue
        await db.users.insert_one({
            "id": new_id(),
            "email": d["email"],
            "password_hash": hash_password(d["password"]),
            "name": d["name"],
            "name_lc": d["name"].lower(),
            "role": d["role"],
            "bio": d["bio"],
            "cover_image": None,
            "avatar": None,
            "approved": True,
            "is_demo": True,
            "stripe_connect_status": "not_started",
            "created_at": now_iso(),
        })
        logger.info(f"Seeded demo account: {d['email']}")
    # Seed settings
    if not await db.settings.find_one({"id": "global"}):
        await db.settings.insert_one({
            "id": "global",
            "commission_percent": 4.0,
            "upload_fee": 5.0,
            "currency": "usd",
            "aotw_artwork_id": None,
            "created_at": now_iso(),
        })


@app.on_event("shutdown")
async def shutdown():
    pass
