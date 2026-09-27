"""CLI-only maintenance: wipe demo-seed docs / junk TEST accounts. Never imported by server.py.

Run via:  cd /app/backend && python seed_demo.py [--wipe-tests]
"""
import logging
from db import db
from seed_demo import SEED, SEEDED_COLLECTIONS

log = logging.getLogger("seed_maintenance")


async def wipe_seed():
    for c in SEEDED_COLLECTIONS:
        r = await db[c].delete_many({"seed": SEED})
        if r.deleted_count:
            log.info("cleared %d from %s", r.deleted_count, c)


async def wipe_tests():
    """Remove junk TEST_* accounts + every doc they own."""
    junk_domains = r"@(test\.com|test\.io|t\.com|t\.io|x\.com|example\.com)$"
    users = await db.users.find({"email": {"$regex": junk_domains}}, {"id": 1}).to_list(5000)
    ids = [u["id"] for u in users]
    if not ids:
        return
    log.info("wiping %d test users", len(ids))
    q_any = {"$in": ids}
    await db.users.delete_many({"id": q_any})
    await db.artworks.delete_many({"$or": [{"artist_id": q_any}, {"title": {"$regex": "^TEST"}}]})
    await db.studio_posts.delete_many({"$or": [{"artist_id": q_any}, {"text": {"$regex": "^TEST_"}}]})
    await db.auctions.delete_many({"seller_id": q_any})
    await db.bids.delete_many({"user_id": q_any})
    await db.events.delete_many({"host_id": q_any})
    await db.event_rsvps.delete_many({"user_id": q_any})
    await db.orders.delete_many({"buyer_id": q_any})
    await db.commissions.delete_many({"$or": [{"buyer_id": q_any}, {"artist_id": q_any}]})
    await db.offers.delete_many({"$or": [{"buyer_id": q_any}, {"artist_id": q_any}]})
    await db.messages.delete_many({"$or": [{"from_id": q_any}, {"to_id": q_any}]})
    await db.notifications.delete_many({"user_id": q_any})
    await db.payment_transactions.delete_many({"user_id": q_any})
    await db.follows.delete_many({"$or": [{"follower_id": q_any}, {"followed_id": q_any}]})
    await db.likes.delete_many({"user_id": q_any})
    await db.comments.delete_many({"user_id": q_any})
    await db.studio_configs.delete_many({"artist_id": q_any})
    # orphan artworks (artist no longer exists) + placeholder images
    live_ids = {u["id"] async for u in db.users.find({}, {"id": 1})}
    orphans = [a["id"] async for a in db.artworks.find({}, {"id": 1, "artist_id": 1}) if a.get("artist_id") not in live_ids]
    if orphans:
        await db.artworks.delete_many({"id": {"$in": orphans}})
        log.info("removed %d orphan artworks", len(orphans))
    await db.artworks.delete_many({"images": {"$in": [["dummy.jpg"], ["a.jpg"]]}})
    await db.auctions.delete_many({"artwork_id": {"$nin": [a["id"] async for a in db.artworks.find({}, {"id": 1})]}})


