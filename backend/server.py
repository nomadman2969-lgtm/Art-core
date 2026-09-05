"""House of Monster — FastAPI backend."""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from db import db, now_iso, new_id
from auth import router as auth_router, hash_password
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
from offers import router as offers_router
from connect import router as connect_router
from push import router as push_router
from events import router as events_router
from storage import init_storage

app = FastAPI(title="Art Core")

app.include_router(auth_router)
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
app.include_router(orders_router)
app.include_router(offers_router)
app.include_router(connect_router)
app.include_router(push_router)
app.include_router(events_router)


@app.get("/api/")
async def root():
    return {"app": "Art Core", "status": "ok"}


@app.get("/api/settings")
async def public_settings():
    s = await db.settings.find_one({"id": "global"})
    if not s:
        s = {"id": "global", "commission_percent": 15.0, "upload_fee": 5.0, "currency": "usd"}
    return {
        "commission_percent": s.get("commission_percent", 15.0),
        "upload_fee": s.get("upload_fee", 5.0),
        "currency": s.get("currency", "usd"),
    }


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup():
    # Init storage
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    # Seed admin
    admin_email = "monster@houseofmonster.com"
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        admin = {
            "id": new_id(),
            "email": admin_email,
            "password_hash": hash_password("MonsterAdmin2026!"),
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

    # Seed demo artist + demo collector (one-click login on /login)
    demo_accounts = [
        {
            "email": "demo.artist@artcorestudio.net",
            "password": "DemoArtist2026!",
            "name": "Demo Artist",
            "role": "artist",
            "bio": "This is a demo artist account. Explore posting artworks, running auctions, and hosting events.",
        },
        {
            "email": "demo.collector@artcorestudio.net",
            "password": "DemoCollector2026!",
            "name": "Demo Collector",
            "role": "buyer",
            "bio": "This is a demo buyer account. Explore browsing, offers, purchases, and RSVPing to events.",
        },
    ]
    for d in demo_accounts:
        if await db.users.find_one({"email": d["email"]}):
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
            "commission_percent": 15.0,
            "upload_fee": 5.0,
            "currency": "usd",
            "aotw_artwork_id": None,
            "created_at": now_iso(),
        })


@app.on_event("shutdown")
async def shutdown():
    pass
