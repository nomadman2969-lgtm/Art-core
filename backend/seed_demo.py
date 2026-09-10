"""Seed a lived-in demo world for Art Core.

Run:  cd /app/backend && python seed_demo.py [--wipe-tests] [--no-images]

Idempotent: everything inserted carries `seed: "demo_v1"` and is replaced on re-run.
Generated images are cached in `demo_assets` so re-runs don't regenerate them.
"""
import asyncio
import base64
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from db import db, new_id, now_iso  # noqa: E402
from auth import hash_password  # noqa: E402
from storage import put_object, compress_image, init_storage, APP_NAME  # noqa: E402
from studio import default_config  # noqa: E402

log = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
random.seed(42)

SEED = "demo_v1"
NOW = datetime.now(timezone.utc)
WIPE_TESTS = "--wipe-tests" in sys.argv
NO_IMAGES = "--no-images" in sys.argv
IMG_MODEL = "gemini-3.1-flash-image-preview"

SEEDED_COLLECTIONS = [
    "users", "artworks", "studio_posts", "post_likes", "post_comments", "auctions", "bids",
    "events", "event_rsvps", "event_waitlist", "orders", "commissions", "offers", "messages",
    "notifications", "payment_transactions", "follows", "likes", "comments", "saves",
    "collections", "reviews", "studio_configs", "watchers",
]


def iso(dt: datetime) -> str:
    return dt.isoformat()


def ago(**kw) -> str:
    return iso(NOW - timedelta(**kw))


def ahead(**kw) -> str:
    return iso(NOW + timedelta(**kw))


# ---------------------------------------------------------------- images
async def register_file(path: str, size: int):
    """The /api/files endpoint only serves paths present in `files`."""
    if not await db.files.find_one({"storage_path": path}):
        await db.files.insert_one({"id": new_id(), "storage_path": path, "user_id": "seed", "original_filename": path.rsplit("/", 1)[-1],
                                   "content_type": "image/jpeg", "size": size, "is_deleted": False, "created_at": now_iso(), "seed": SEED})


async def gen_image(slug: str, prompt: str, aspect: str = "square") -> str | None:
    """Generate (or fetch cached) image → returns storage path."""
    cached = await db.demo_assets.find_one({"slug": slug})
    if cached:
        await register_file(cached["path"], 0)
        return cached["path"]
    if NO_IMAGES:
        return None
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"seed-{slug}-{new_id()[:6]}",
                   system_message="You are an image generator. Output only the image.")
    chat.with_model("gemini", IMG_MODEL).with_params(modalities=["image", "text"])
    shape = {"square": "square 1:1", "wide": "wide 16:9 landscape", "tall": "portrait 3:4"}[aspect]
    for attempt in range(3):
        try:
            _, images = await chat.send_message_multimodal_response(UserMessage(text=f"{prompt}. {shape} composition, no text, no watermark, no captions."))
            if images:
                raw = base64.b64decode(images[0]["data"])
                data = compress_image(raw, max_dim=1400, quality=82)
                path = f"{APP_NAME}/demo/{slug}.jpg"
                put_object(path, data, "image/jpeg")
                await db.demo_assets.insert_one({"slug": slug, "path": path, "created_at": now_iso()})
                await register_file(path, len(data))
                log.info("generated %s (%d KB)", slug, len(data) // 1024)
                return path
        except Exception as e:  # noqa
            log.warning("image %s attempt %d failed: %s", slug, attempt + 1, str(e)[:120])
            await asyncio.sleep(2)
    return None


_sem = asyncio.Semaphore(4)


async def gen(slug, prompt, aspect="square"):
    async with _sem:
        return await gen_image(slug, prompt, aspect)


# ---------------------------------------------------------------- data
ARTISTS = [
    dict(key="kai", name="Kai Rivera", email="kai@demo.artcorestudio.net", city="Brooklyn, NY", style="Graffiti / Street",
         bio="Bushwick-raised graffiti writer turned canvas artist. Wildstyle letters, chrome fades, and a lot of spray fumes.",
         theme="urban_graffiti", avatar="close-up portrait of a young latino street artist wearing a paint-splattered hoodie and respirator around neck, brooklyn rooftop at dusk, cinematic photo"),
    dict(key="yuki", name="Yuki Tanaka", email="yuki@demo.artcorestudio.net", city="Tokyo, JP", style="Neon Digital",
         bio="Digital painter obsessed with rain-soaked Shinjuku alleys, holograms, and the color cyan.",
         theme="neon_digital", avatar="portrait of a japanese woman digital artist with short violet hair lit by neon signs in tokyo at night, cinematic photo"),
    dict(key="marisol", name="Marisol Vega", email="marisol@demo.artcorestudio.net", city="Mexico City, MX", style="Abstract Oil",
         bio="Large-format abstract oils. Colour as weather. Studio in Roma Norte, doors always open.",
         theme="luxury_gallery", avatar="portrait of a mexican woman painter in her 40s in a sunlit studio with big abstract canvases behind her, warm photo"),
    dict(key="theo", name="Theo Lindqvist", email="theo@demo.artcorestudio.net", city="Stockholm, SE", style="Minimal Sculpture",
         bio="Bronze, concrete and birch. I make quiet objects for loud rooms.",
         theme="minimal", avatar="portrait of a scandinavian male sculptor with beard in a white minimalist studio, soft daylight, photo"),
    dict(key="amara", name="Amara Okafor", email="amara@demo.artcorestudio.net", city="London, UK", style="Figurative Portraits",
         bio="Portraits of people who don't usually get painted. Oil on linen, gold leaf when they deserve it.",
         theme="dark_gallery", avatar="portrait of a black british woman painter with locs, holding a brush, dramatic studio lighting, photo"),
    dict(key="dex", name="Dex Morrow", email="dex@demo.artcorestudio.net", city="Los Angeles, CA", style="Pop Surrealism",
         bio="Lowbrow pop surrealism. Melting cartoons, chrome skulls, Californian sunsets that feel slightly wrong.",
         theme="industrial", avatar="portrait of a tattooed male pop-surrealist artist with sunglasses in a los angeles garage studio, photo"),
    dict(key="ines", name="Inês Duarte", email="ines@demo.artcorestudio.net", city="Lisbon, PT", style="Analog Photography",
         bio="Medium-format film. Tiled facades, empty pools, and the Atlantic light.",
         theme="minimal", avatar="portrait of a portuguese woman photographer holding a medium format film camera on a lisbon street, photo"),
]

COLLECTORS = [
    dict(key="jordan", name="Jordan Blake", email="jordan@demo.artcorestudio.net", bio="Collector of loud things. Brooklyn."),
    dict(key="priya", name="Priya Nair", email="priya@demo.artcorestudio.net", bio="Interior designer hunting statement pieces for clients."),
    dict(key="luca", name="Luca Moretti", email="luca@demo.artcorestudio.net", bio="First-time collector. Started with prints, now can't stop."),
]

# artist_key, slug, title, medium, price, status, w, h, prompt, style_tag
ARTWORKS = [
    ("demo", "demo-neon-alley", "Neon Alley No. 4", "Acrylic", 1200, "live", 30, 40, "vibrant acrylic painting of a rain-slicked graffiti alley lit by lime green and violet neon, thick brushstrokes, street art gallery piece", "urban"),
    ("demo", "demo-chrome-heart", "Chrome Heart", "Mixed Media", 850, "live", 24, 24, "mixed media artwork of a chrome anatomical heart dripping spray paint on raw concrete texture, graffiti style", "urban"),
    ("demo", "demo-signal-lost", "Signal Lost", "Digital", 320, "live", 18, 24, "glitchy digital painting of a distorted cyan face dissolving into pixel noise on black, contemporary digital art", "digital"),
    ("demo", "demo-wildstyle-01", "Wildstyle Study I", "Acrylic", 640, "sold", 20, 20, "wildstyle graffiti letters in gold and black on a canvas, sharp arrows and 3d shadows, spray paint texture", "urban"),
    ("demo", "demo-midnight-bodega", "Midnight Bodega", "Oil", 2400, "live", 36, 48, "moody oil painting of a brooklyn bodega storefront at midnight, neon lights reflecting on wet pavement, edward hopper meets street art", "urban"),
    ("demo", "demo-tag-series", "Tag Series (Print 3/25)", "Print", 95, "live", 12, 16, "bold screen print of layered graffiti tags in lime, magenta and black on cream paper, limited edition print", "urban"),
    ("kai", "kai-bushwick-burner", "Bushwick Burner", "Acrylic", 1800, "live", 40, 30, "explosive wildstyle graffiti burner with chrome fades and hot pink drips painted on canvas, photorealistic paint texture", "urban"),
    ("kai", "kai-throwie-gold", "Throwie in Gold", "Mixed Media", 700, "live", 24, 24, "gold leaf graffiti throw-up letters on a distressed black canvas with drips, luxury street art", "urban"),
    ("kai", "kai-rooftop-crew", "Rooftop Crew", "Acrylic", 2200, "live", 48, 36, "graffiti-style painting of silhouetted figures on a brooklyn rooftop at dusk with a giant spray-painted skyline", "urban"),
    ("kai", "kai-subway-map", "Subway Map (Remixed)", "Print", 120, "live", 18, 24, "screen print of a new york subway map remixed with graffiti tags and neon colors, limited edition", "urban"),
    ("yuki", "yuki-shinjuku-rain", "Shinjuku Rain", "Digital", 480, "live", 24, 32, "cyberpunk digital painting of a rainy shinjuku alley with cyan and magenta neon signs and umbrellas, highly detailed", "digital"),
    ("yuki", "yuki-hologram-koi", "Hologram Koi", "Digital", 390, "live", 24, 24, "digital artwork of translucent holographic koi fish swimming through a dark neon city, glowing cyan and orange", "digital"),
    ("yuki", "yuki-vending-machine", "Vending Machine 3AM", "Digital", 420, "sold", 20, 28, "digital painting of a lone glowing japanese vending machine on an empty street at 3am, purple fog, cinematic", "digital"),
    ("marisol", "marisol-tormenta", "Tormenta", "Oil", 3600, "live", 60, 48, "large abstract expressionist oil painting with storm-like sweeps of deep blue, ochre and white impasto", "abstract"),
    ("marisol", "marisol-calor", "Calor", "Oil", 2900, "live", 48, 48, "abstract oil painting of heat, saturated reds oranges and pink with thick palette knife texture", "abstract"),
    ("marisol", "marisol-lluvia", "Lluvia de Mayo", "Watercolor", 650, "live", 18, 24, "loose abstract watercolor with vertical rain-like streaks of teal and violet bleeding into paper", "abstract"),
    ("theo", "theo-still-form", "Still Form II", "Sculpture", 4200, "live", 14, 22, "photograph of a minimalist bronze and concrete sculpture, smooth curved form on a white plinth in a gallery, soft daylight", "minimal"),
    ("theo", "theo-birch-arc", "Birch Arc", "Sculpture", 1900, "live", 30, 18, "photograph of a bent pale birch wood arc sculpture on a concrete floor in a white minimalist room", "minimal"),
    ("amara", "amara-auntie", "Auntie Grace, Sunday", "Oil", 5400, "live", 36, 48, "oil portrait of an elderly black woman in a sunday hat with gold leaf background, kehinde wiley inspired, rich detail", "figurative"),
    ("amara", "amara-boy-blue", "Boy in Blue Light", "Oil", 3100, "sold", 24, 30, "oil portrait of a young black boy lit by blue light against dark green foliage pattern background, painterly", "figurative"),
    ("amara", "amara-sisters", "Sisters", "Oil", 4800, "live", 40, 40, "oil painting of two young women in bright patterned dresses sitting on a london stoop, warm and painterly", "figurative"),
    ("dex", "dex-melting-mickey", "Melt (Sunset Edition)", "Acrylic", 1500, "live", 30, 30, "pop surrealism painting of a melting cartoon character dripping over a california sunset, chrome highlights, lowbrow art", "pop"),
    ("dex", "dex-chrome-skull", "Chrome Skull, Palm Trees", "Acrylic", 1250, "live", 24, 30, "pop surrealist painting of a shiny chrome skull wearing sunglasses in front of pink palm trees, glossy finish", "pop"),
    ("dex", "dex-sticker-bomb", "Sticker Bomb", "Print", 80, "live", 18, 18, "dense sticker-bomb style print with dozens of cartoon eyes, flames and slogans-free shapes, saturated colors", "pop"),
    ("ines", "ines-alfama-tiles", "Alfama Tiles", "Photography", 540, "live", 20, 30, "medium format film photograph of a lisbon facade with blue azulejo tiles and a single yellow window, soft atlantic light", "photo"),
    ("ines", "ines-empty-pool", "Empty Pool, August", "Photography", 620, "live", 24, 36, "analog film photograph of an empty turquoise swimming pool with long shadows at golden hour, minimal composition", "photo"),
    ("ines", "ines-tram-28", "Tram 28", "Photography", 480, "sold", 20, 30, "film photograph of a yellow vintage lisbon tram on a steep cobblestone street, grainy kodak portra look", "photo"),
]

EVENT_COVERS = {
    "ev-neon-rooftop": "wide photo of a brooklyn rooftop art party at night with neon-lit canvases, string lights and a crowd, cinematic",
    "ev-live-battle": "wide photo of two graffiti artists painting giant canvases on a stage in front of a cheering crowd, colorful spray paint",
    "ev-sketch-club": "wide photo of a cozy sunday sketch club, people drawing at long wooden tables with coffee cups and sketchbooks, warm light",
    "ev-tokyo-neon": "wide cyberpunk illustration of a virtual gallery floating above tokyo with neon holograms",
    "ev-print-market": "wide photo of an outdoor art print market in mexico city with colorful stalls and papel picado, sunny",
    "ev-fig-workshop": "wide photo of a figurative painting workshop in a london studio, easels in a circle, natural light",
    "ev-open-studio": "wide photo of an open studio day, visitors looking at paintings leaning against brick walls, afternoon light",
}

POST_IMAGES = {
    "wip-neon-alley": "photo of an unfinished acrylic painting of a neon alley on an easel in a messy studio, paint tubes and brushes in foreground",
    "studio-photo-demo": "photo of a graffiti artist studio with spray cans organized by color on shelves and canvases on the wall, moody light",
    "wip-koi": "screenshot-style photo of a digital painting tablet showing a half-finished neon koi illustration, desk with stylus",
    "bts-marisol": "photo of a painter's hands covered in blue and ochre oil paint holding a palette knife over a huge canvas",
}


# ---------------------------------------------------------------- helpers
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


def notif(user_id, kind, **extra):
    return {"id": new_id(), "user_id": user_id, "kind": kind, "read": extra.pop("read", False),
            "created_at": extra.pop("created_at", now_iso()), "seed": SEED, **extra}


def dm(frm, to, text, at, attachment=None, read=True):
    return {
        "id": new_id(), "thread_key": "::".join(sorted([frm["id"], to["id"]])),
        "from_id": frm["id"], "from_name": frm["name"], "to_id": to["id"], "to_name": to["name"],
        "text": text, "attachment": attachment, "read": read, "delivered_at": at,
        "read_at": at if read else None, "created_at": at, "seed": SEED,
    }


# ---------------------------------------------------------------- main
async def main():
    init_storage()
    if WIPE_TESTS:
        await wipe_tests()
    await wipe_seed()

    # --- protagonists (already seeded at startup)
    demo_artist = await db.users.find_one({"email": "demo.artist@artcorestudio.net"})
    demo_collector = await db.users.find_one({"email": "demo.collector@artcorestudio.net"})
    if not demo_artist or not demo_collector:
        raise SystemExit("Start the backend once first so demo accounts exist.")

    # --- images (parallel)
    log.info("generating images…")
    tasks = {}
    for a in ARTISTS:
        tasks[f"avatar-{a['key']}"] = gen(f"avatar-{a['key']}", a["avatar"])
    tasks["avatar-demo"] = gen("avatar-demo", "portrait of a confident young artist with paint on their cheek in front of a lime-green graffiti wall, photo")
    tasks["avatar-collector"] = gen("avatar-collector", "portrait of a stylish art collector in a dark gallery holding a glass of wine, soft light, photo")
    for (_k, slug, _t, _m, _p, _s, w, h, prompt, _tag) in ARTWORKS:
        tasks[slug] = gen(slug, prompt, "tall" if h > w else ("wide" if w > h else "square"))
    for slug, prompt in EVENT_COVERS.items():
        tasks[slug] = gen(slug, prompt, "wide")
    for slug, prompt in POST_IMAGES.items():
        tasks[slug] = gen(slug, prompt, "square")
    results = await asyncio.gather(*tasks.values())
    IMG = dict(zip(tasks.keys(), results))
    log.info("images ready: %d/%d", sum(1 for v in IMG.values() if v), len(IMG))

    # --- users
    users = {"demo": demo_artist, "collector": demo_collector}
    await db.users.update_one({"id": demo_artist["id"]}, {"$set": {
        "avatar": IMG.get("avatar-demo"), "cover_image": IMG.get("demo-neon-alley"),
        "bio": "Brooklyn-based street artist. Neon, chrome, and letters that bite. This is the demo artist account — everything here is yours to explore.",
    }})
    await db.users.update_one({"id": demo_collector["id"]}, {"$set": {"avatar": IMG.get("avatar-collector")}})
    for a in ARTISTS:
        u = {"id": new_id(), "email": a["email"], "password_hash": hash_password("DemoArtist2026!"), "name": a["name"],
             "name_lc": a["name"].lower(), "role": "artist", "bio": a["bio"], "avatar": IMG.get(f"avatar-{a['key']}"),
             "cover_image": None, "approved": True, "is_demo": True, "stripe_connect_status": "not_started",
             "created_at": ago(days=random.randint(60, 300)), "seed": SEED}
        await db.users.insert_one(u)
        users[a["key"]] = u
    for c in COLLECTORS:
        u = {"id": new_id(), "email": c["email"], "password_hash": hash_password("DemoCollector2026!"), "name": c["name"],
             "name_lc": c["name"].lower(), "role": "buyer", "bio": c["bio"], "avatar": None, "cover_image": None,
             "approved": True, "is_demo": True, "created_at": ago(days=random.randint(30, 200)), "seed": SEED}
        await db.users.insert_one(u)
        users[c["key"]] = u

    # --- studio configs
    for a in ARTISTS + [dict(key="demo", theme="urban_graffiti", city="Brooklyn, NY", style="Graffiti / Neon")]:
        u = users[a["key"]]
        cfg = default_config(u["id"])
        cfg.update({"theme": a["theme"], "seed": SEED})
        cfg["artist_story"].update({"location": a["city"], "style": a["style"], "years_active": random.randint(3, 15),
                                    "influences": "Basquiat, Futura, the L train", "instagram": a["key"] + ".art"})
        cfg["visits"] = random.randint(120, 2400)
        await db.studio_configs.delete_many({"artist_id": u["id"]})
        await db.studio_configs.insert_one(cfg)
    # set cover images for artists from their first artwork
    for a in ARTISTS:
        first = next((s for (k, s, *_r) in ARTWORKS if k == a["key"]), None)
        if first:
            await db.users.update_one({"id": users[a["key"]]["id"]}, {"$set": {"cover_image": IMG.get(first)}})

    # --- artworks
    ART = {}
    for i, (k, slug, title, medium, price, status, w, h, prompt, tag) in enumerate(ARTWORKS):
        img = IMG.get(slug)
        doc = {
            "id": new_id(), "artist_id": users[k]["id"], "title": title,
            "description": f"{title} — {medium.lower()} on {'paper' if medium in ('Print', 'Watercolor', 'Photography') else 'canvas'}, {w}×{h} in. {prompt.split(',')[0].capitalize()}.",
            "medium": medium, "style": tag, "color": None, "width_in": float(w), "height_in": float(h),
            "price": float(price), "images": [img] if img else [], "status": status,
            "kind": "print" if medium == "Print" else ("digital" if medium == "Digital" else "original"),
            "quantity": 25 if medium == "Print" else 1, "tags": [tag, medium.lower()], "year": 2026,
            "featured": slug in ("amara-auntie", "marisol-tormenta", "kai-bushwick-burner", "demo-midnight-bodega"),
            "aotw": slug == "amara-auntie", "aotw_submitted": False,
            "like_count": random.randint(4, 140), "view_count": random.randint(80, 3200),
            "created_at": ago(days=random.randint(2, 45), hours=i), "seed": SEED,
        }
        await db.artworks.insert_one(doc)
        ART[slug] = doc

    # --- follows
    follows = []
    for k in [a["key"] for a in ARTISTS] + ["demo"]:
        follows.append((users["collector"], users[k]))
    for k in ["jordan", "priya", "luca", "kai", "yuki", "amara"]:
        follows.append((users[k], users["demo"]))
    for k in ["jordan", "priya"]:
        for t in ["kai", "amara", "marisol"]:
            follows.append((users[k], users[t]))
    for f, t in follows:
        await db.follows.insert_one({"id": new_id(), "follower_id": f["id"], "followed_id": t["id"], "created_at": ago(days=random.randint(1, 60)), "seed": SEED})

    # --- likes + comments + saves
    likers = ["collector", "jordan", "priya", "luca", "kai", "yuki", "amara", "dex"]
    for slug, art in ART.items():
        for lk in random.sample(likers, k=random.randint(2, 5)):
            if users[lk]["id"] == art["artist_id"]:
                continue
            await db.likes.insert_one({"id": new_id(), "user_id": users[lk]["id"], "artwork_id": art["id"], "created_at": ago(days=random.randint(0, 20)), "seed": SEED})
    comment_bank = [
        "The colour in this is unreal.", "Need this on my wall yesterday.", "That texture 🔥", "Saw this in person — photos don't do it justice.",
        "Is this still available?", "Framed or unframed?", "This one stopped me mid-scroll.", "The drips!!",
    ]
    for slug in ["demo-neon-alley", "demo-midnight-bodega", "kai-bushwick-burner", "amara-auntie", "marisol-tormenta", "yuki-shinjuku-rain", "dex-melting-mickey"]:
        art = ART[slug]
        parent = {"id": new_id(), "artwork_id": art["id"], "user_id": users["collector"]["id"], "user_name": "Demo Collector",
                  "text": random.choice(comment_bank), "parent_id": None, "mentions": [], "reply_count": 1, "created_at": ago(days=3), "seed": SEED}
        await db.comments.insert_one(parent)
        artist = await db.users.find_one({"id": art["artist_id"]})
        await db.comments.insert_one({"id": new_id(), "artwork_id": art["id"], "user_id": artist["id"], "user_name": artist["name"],
                                      "text": "Thank you! Yes, still available — DM me for shipping.", "parent_id": parent["id"], "mentions": [], "reply_count": 0, "created_at": ago(days=2), "seed": SEED})
        for extra in random.sample(["jordan", "priya", "luca"], 2):
            await db.comments.insert_one({"id": new_id(), "artwork_id": art["id"], "user_id": users[extra]["id"], "user_name": users[extra]["name"],
                                          "text": random.choice(comment_bank), "parent_id": None, "mentions": [], "reply_count": 0, "created_at": ago(days=random.randint(1, 10)), "seed": SEED})
    col = {"id": new_id(), "user_id": users["collector"]["id"], "name": "Neon Dreams", "description": "Everything that glows.", "is_private": False, "created_at": ago(days=12), "seed": SEED}
    await db.collections.insert_one(col)
    for slug in ["demo-neon-alley", "yuki-shinjuku-rain", "yuki-hologram-koi", "demo-signal-lost"]:
        await db.saves.insert_one({"id": new_id(), "user_id": users["collector"]["id"], "artwork_id": ART[slug]["id"], "collection_id": col["id"], "created_at": ago(days=random.randint(1, 11)), "seed": SEED})
    for slug in ["amara-auntie", "theo-still-form"]:
        await db.saves.insert_one({"id": new_id(), "user_id": users["collector"]["id"], "artwork_id": ART[slug]["id"], "collection_id": None, "created_at": ago(days=1), "seed": SEED})

    # --- studio posts (feed)
    POSTS = [
        ("demo", "wip", "Blocking in the neon for Neon Alley No. 5. The green is fighting the violet and honestly I'm letting them.", IMG.get("wip-neon-alley"), ago(hours=3), True),
        ("demo", "sold", "SOLD — Wildstyle Study I is off to a new home in Chicago. Thank you @Demo Collector 🙏", IMG.get("demo-wildstyle-01"), ago(days=1), False),
        ("demo", "auction", "Chrome Heart goes to auction tonight. Starting at $400, no reserve. Ends in a few hours — go get it.", IMG.get("demo-chrome-heart"), ago(hours=6), False),
        ("demo", "exhibition", "SOLO SHOW: 'Neon Rooftop' — one night only in Bushwick. Tickets are live on the Events tab, 60 spots.", IMG.get("ev-neon-rooftop"), ago(days=2), False),
        ("demo", "studio_photo", "Reorganised the cans by hue. It lasted eleven minutes.", IMG.get("studio-photo-demo"), ago(days=4), False),
        ("demo", "commission", "Commissions are OPEN for summer — 3 slots. Portraits, letter pieces, murals. Hit the Request button on my studio.", None, ago(days=5), False),
        ("kai", "wip", "Day 3 on Bushwick Burner. Chrome fades are the hardest thing in the world and I love them.", IMG.get("kai-bushwick-burner"), ago(hours=9), False),
        ("kai", "event", "Sunday Sketch Club is back — every Sunday at the Bushwick studio. Free, bring a pen.", IMG.get("ev-sketch-club"), ago(days=3), False),
        ("yuki", "wip", "Koi #3 in progress. Trying to make light feel wet.", IMG.get("wip-koi"), ago(hours=14), False),
        ("yuki", "sold", "Vending Machine 3AM found a home in Berlin. Arigatou 🥲", IMG.get("yuki-vending-machine"), ago(days=6), False),
        ("marisol", "behind_scenes", "Ochre, cobalt, and a palette knife the size of a spatula. Tormenta is almost done.", IMG.get("bts-marisol"), ago(days=1, hours=2), False),
        ("amara", "announcement", "'Auntie Grace, Sunday' was selected as Featured Piece this week. Overwhelmed. She would have laughed.", IMG.get("amara-auntie"), ago(days=2, hours=5), True),
        ("amara", "sold", "Boy in Blue Light — SOLD. Off to a collector in Lagos.", IMG.get("amara-boy-blue"), ago(days=8), False),
        ("dex", "update", "New drop Friday: Sticker Bomb prints, edition of 50, $80. Chrome skull sold out in 2 hours last time so.", IMG.get("dex-sticker-bomb"), ago(days=1, hours=8), False),
        ("theo", "studio_photo", "Still Form II under morning light. Bronze is patient.", IMG.get("theo-still-form"), ago(days=3, hours=1), False),
        ("ines", "exhibition", "Alfama Tiles will be showing at the Lisbon print market this month. Come say olá.", IMG.get("ines-alfama-tiles"), ago(days=4, hours=6), False),
    ]
    POST_IDS = []
    for k, kind, text, image, at, pinned in POSTS:
        p = {"id": new_id(), "artist_id": users[k]["id"], "artist_name": users[k]["name"], "kind": kind, "text": text,
             "image": image, "video": None, "pinned": pinned, "mentions": [], "like_count": 0, "comment_count": 0, "created_at": at, "seed": SEED}
        await db.studio_posts.insert_one(p)
        POST_IDS.append(p)
        for lk in random.sample(likers, k=random.randint(1, 5)):
            if users[lk]["id"] == p["artist_id"]:
                continue
            await db.post_likes.insert_one({"id": new_id(), "post_id": p["id"], "user_id": users[lk]["id"], "created_at": at, "seed": SEED})
            await db.studio_posts.update_one({"id": p["id"]}, {"$inc": {"like_count": 1}})
    for p in POST_IDS[:4]:
        await db.post_comments.insert_one({"id": new_id(), "post_id": p["id"], "user_id": users["collector"]["id"], "user_name": "Demo Collector",
                                           "text": random.choice(["Can't wait to see this finished!", "Take my money.", "Congrats!!", "See you there 🎟️"]),
                                           "mentions": [], "created_at": now_iso(), "seed": SEED})
        await db.studio_posts.update_one({"id": p["id"]}, {"$inc": {"comment_count": 1}})

    # --- auctions
    async def auction(slug, start, end, status, bids, reserve=0, winner_paid=False):
        art = ART[slug]
        doc = {"id": new_id(), "artwork_id": art["id"], "seller_id": art["artist_id"], "start_price": float(bids[0][1] if bids else art["price"] * 0.4),
               "reserve_price": float(reserve), "current_bid": None, "current_bidder_id": None, "current_bidder_name": None, "bid_count": 0,
               "start_at": start, "started_at": start if status != "scheduled" else None, "end_at": end, "status": status,
               "winner_id": None, "final_price": None, "created_at": start, "seed": SEED}
        t = datetime.fromisoformat(start)
        for i, (who, amt) in enumerate(bids):
            t = t + timedelta(minutes=random.randint(20, 400))
            await db.bids.insert_one({"id": new_id(), "auction_id": doc["id"], "user_id": users[who]["id"], "user_name": users[who]["name"], "amount": float(amt), "created_at": iso(min(t, NOW - timedelta(minutes=1))), "seed": SEED})
            doc.update({"current_bid": float(amt), "current_bidder_id": users[who]["id"], "current_bidder_name": users[who]["name"], "bid_count": i + 1})
        if status == "ended":
            won = doc["current_bid"] and doc["current_bid"] >= reserve
            doc.update({"winner_id": doc["current_bidder_id"] if won else None, "final_price": doc["current_bid"] if won else None,
                        "ended_at": end, "payment_deadline": iso(datetime.fromisoformat(end) + timedelta(hours=48))})
            if won:
                await db.artworks.update_one({"id": art["id"]}, {"$set": {"status": "sold"}})
                if winner_paid:
                    doc.update({"paid": True, "paid_at": end})
        await db.auctions.insert_one(doc)
        return doc

    au_live_soon = await auction("demo-chrome-heart", ago(hours=6), ahead(minutes=42), "live", [("jordan", 400), ("collector", 450), ("priya", 520), ("collector", 600)])
    au_live_2 = await auction("kai-throwie-gold", ago(days=1), ahead(days=2, hours=3), "live", [("collector", 350), ("luca", 400), ("jordan", 475)])
    au_live_3 = await auction("marisol-calor", ago(days=2), ahead(days=5), "live", [("priya", 1500), ("jordan", 1700)], reserve=2000)
    await auction("dex-chrome-skull", ahead(days=1, hours=4), ahead(days=4, hours=4), "scheduled", [])
    await auction("theo-birch-arc", ahead(days=3), ahead(days=10), "scheduled", [], reserve=1500)
    au_won = await auction("yuki-vending-machine", ago(days=3), ago(hours=9), "ended", [("jordan", 200), ("collector", 260), ("jordan", 300), ("collector", 340)])
    au_sold_paid = await auction("amara-boy-blue", ago(days=12), ago(days=8), "ended", [("priya", 1800), ("luca", 2100), ("priya", 2600)], winner_paid=True)
    au_sold_paid2 = await auction("ines-tram-28", ago(days=20), ago(days=15), "ended", [("collector", 300), ("jordan", 340), ("collector", 400)], winner_paid=True)
    for w in ["collector", "luca"]:
        await db.watchers.insert_one({"id": new_id(), "auction_id": au_live_3["id"], "user_id": users[w]["id"], "created_at": ago(days=1), "seed": SEED})

    # --- orders
    async def order(buyer, slug, total, created, ful, source=None, review=None, payout="pending"):
        art = ART[slug]
        o = {"id": f"order_{new_id()[:8]}", "session_id": f"cs_demo_{new_id()[:10]}", "buyer_id": users[buyer]["id"],
             "items": [{"artwork_id": art["id"], "artist_id": art["artist_id"], "price": float(total), "quantity": 1}],
             "total": float(total), "currency": "usd", "commission_percent": 15,
             "platform_take": round(total * 0.15, 2),
             "artist_payouts": [{"artist_id": art["artist_id"], "artwork_id": art["id"], "gross": float(total), "net": round(total * 0.85, 2), "status": payout}],
             "fulfillment": ful, "created_at": created, "seed": SEED}
        if source:
            o["source"] = "auction"; o["auction_id"] = source["id"]
        await db.orders.insert_one(o)
        await db.artworks.update_one({"id": art["id"]}, {"$set": {"status": "sold"}})
        if review:
            await db.reviews.insert_one({"id": new_id(), "order_id": o["id"], "artwork_id": art["id"], "artist_id": art["artist_id"], "buyer_id": users[buyer]["id"],
                                         "buyer_name": users[buyer]["name"], "rating": review[0], "text": review[1], "created_at": ful.get("delivered_at") or created, "seed": SEED})
        return o

    o_delivered = await order("collector", "ines-tram-28", 400, ago(days=15), {"status": "delivered", "shipped_at": ago(days=13), "delivered_at": ago(days=9), "tracking": "1Z999AA10123456784", "carrier": "UPS"},
                              source=au_sold_paid2, review=(5, "Arrived perfectly packed. The grain on this print is gorgeous in person."), payout="released")
    o_shipped = await order("collector", "demo-wildstyle-01", 640, ago(days=2), {"status": "shipped", "shipped_at": ago(days=1), "delivered_at": None, "tracking": "9400111899223197428490", "carrier": "USPS"})
    await order("priya", "amara-boy-blue", 2600, ago(days=8), {"status": "delivered", "shipped_at": ago(days=7), "delivered_at": ago(days=3), "tracking": "JD014600003456789012", "carrier": "DHL"},
                source=au_sold_paid, review=(5, "Amara is the real deal. The blue light in this piece changes with the room."), payout="released")
    await order("luca", "demo-tag-series", 95, ago(hours=5), {"status": "pending", "shipped_at": None, "delivered_at": None, "tracking": None, "carrier": None})
    await db.artworks.update_one({"id": ART["demo-tag-series"]["id"]}, {"$set": {"status": "live", "quantity": 22}})  # prints stay live

    # --- offers
    async def offer(buyer, slug, amount, status, created, counter=None, history_extra=None):
        art = ART[slug]
        o = {"id": new_id(), "artwork_id": art["id"], "artist_id": art["artist_id"], "buyer_id": users[buyer]["id"], "buyer_name": users[buyer]["name"],
             "list_price": art["price"], "amount": float(amount), "counter_amount": counter, "message": "Love this piece — would you take this?",
             "status": status, "history": [{"kind": "buyer_offer", "amount": float(amount), "at": created, "message": "Love this piece — would you take this?"}] + (history_extra or []),
             "paid": False, "created_at": created, "updated_at": now_iso(), "seed": SEED}
        await db.offers.insert_one(o)
        return o

    of_pending = await offer("collector", "demo-midnight-bodega", 2000, "pending", ago(hours=4))
    of_countered = await offer("collector", "kai-rooftop-crew", 1600, "countered", ago(days=1), counter=1950.0, history_extra=[{"kind": "seller_counter", "amount": 1950.0, "at": ago(hours=20)}])
    of_accepted = await offer("collector", "dex-melting-mickey", 1300, "accepted", ago(days=2), history_extra=[{"kind": "seller_accept", "at": ago(days=1, hours=20)}])
    await offer("jordan", "demo-neon-alley", 950, "pending", ago(hours=1))
    await offer("priya", "demo-signal-lost", 260, "declined", ago(days=3), history_extra=[{"kind": "seller_decline", "at": ago(days=2)}])

    # --- commissions
    async def commission(buyer, artist, subject, style, size, budget, status, created, progress, extra=None):
        c = {"id": new_id(), "buyer_id": users[buyer]["id"], "artist_id": users[artist]["id"], "subject": subject, "style": style, "size": size,
             "budget": float(budget), "deadline": ahead(days=30)[:10], "instructions": "Reference photos attached. Open to your interpretation — surprise me.",
             "reference_images": [], "status": status, "counter_amount": None, "progress": progress, "final_images": [],
             "created_at": created, "updated_at": now_iso(), "seed": SEED, **(extra or {})}
        await db.commissions.insert_one(c)
        return c

    c_progress = await commission("collector", "demo", "Neon portrait of my dog Biscuit", "Graffiti / neon", "24x30", 900, "in_progress", ago(days=6),
                                  [{"kind": "artist_accept", "message": "Biscuit deserves chrome. Let's go.", "at": ago(days=5)},
                                   {"kind": "deposit_paid", "amount": 450.0, "at": ago(days=5, hours=-2)},
                                   {"kind": "artist_update", "message": "Sketch locked. Blocking in the background tonight.", "image": IMG.get("wip-neon-alley"), "at": ago(days=2)}],
                                  extra={"deposit_paid": True, "deposit_amount": 450.0, "deposit_paid_at": ago(days=5)})
    c_delivered = await commission("collector", "amara", "Portrait of my grandmother", "Oil on linen", "20x24", 2200, "delivered", ago(days=40),
                                   [{"kind": "artist_accept", "message": "It would be an honour.", "at": ago(days=39)},
                                    {"kind": "deposit_paid", "amount": 1100.0, "at": ago(days=38)},
                                    {"kind": "artist_update", "message": "Underpainting done.", "at": ago(days=20)},
                                    {"kind": "artist_delivered", "message": "She's finished. I hope she feels like home.", "at": ago(days=1)}],
                                   extra={"deposit_paid": True, "deposit_amount": 1100.0, "final_images": [IMG.get("amara-auntie")] if IMG.get("amara-auntie") else []})
    c_pending = await commission("jordan", "demo", "Wildstyle piece for my bar", "Graffiti", "48x72", 3500, "pending", ago(hours=2), [])
    c_counter = await commission("luca", "demo", "Small letter study", "Graffiti", "12x12", 200, "counter", ago(days=1),
                                 [{"kind": "artist_counter", "message": "Can do this at $320 with a frame.", "amount": 320.0, "at": ago(hours=18)}], extra={"counter_amount": 320.0})
    await commission("priya", "demo", "Neon storefront for a client lobby", "Acrylic / neon", "36x48", 2800, "paid", ago(days=60),
                     [{"kind": "artist_accept", "at": ago(days=59)}, {"kind": "deposit_paid", "amount": 1400.0, "at": ago(days=58)},
                      {"kind": "artist_update", "message": "Halfway.", "at": ago(days=40)}, {"kind": "artist_delivered", "message": "Done!", "at": ago(days=22)},
                      {"kind": "buyer_approved", "at": ago(days=21)}],
                     extra={"deposit_paid": True, "deposit_amount": 1400.0, "paid": True, "paid_at": ago(days=21), "final_images": [IMG.get("demo-midnight-bodega")] if IMG.get("demo-midnight-bodega") else []})

    # --- events
    async def event(host, slug, title, desc, cat, loc, start, hours, cover, cap=None, price=None, series=None, created=None):
        e = {"id": new_id(), "host_id": users[host]["id"], "host_name": users[host]["name"], "title": title, "description": desc, "category": cat,
             "location": loc, "start_at": start, "end_at": iso(datetime.fromisoformat(start) + timedelta(hours=hours)), "cover_image": IMG.get(cover),
             "max_capacity": cap, "is_free": price is None, "ticket_price": price, "cancelled": False,
             "series_id": series[0] if series else None, "series_seq": series[1] if series else None, "series_total": series[2] if series else None,
             "reminders_enabled": True, "created_at": created or ago(days=random.randint(5, 20)), "seed": SEED}
        await db.events.insert_one(e)
        return e

    async def rsvp(ev, who, created, paid=None, checked_in=False):
        r = {"id": new_id(), "event_id": ev["id"], "user_id": users[who]["id"], "user_name": users[who]["name"], "created_at": created, "seed": SEED}
        if paid:
            sid = f"cs_demo_{new_id()[:10]}"
            r.update({"paid": True, "amount": float(paid), "session_id": sid, "payment_intent": f"pi_demo_{new_id()[:10]}"})
            await db.payment_transactions.insert_one({"id": new_id(), "session_id": sid, "payment_intent": r["payment_intent"], "kind": "event_ticket", "user_id": users[who]["id"],
                                                      "event_id": ev["id"], "host_id": ev["host_id"], "amount": float(paid), "currency": "usd", "status": "complete",
                                                      "payment_status": "paid", "created_at": created, "updated_at": created, "seed": SEED})
        if checked_in:
            r.update({"checked_in": True, "checked_in_at": iso(datetime.fromisoformat(ev["start_at"]) + timedelta(minutes=random.randint(5, 50)))})
        await db.event_rsvps.insert_one(r)
        return r

    BK = {"lat": 40.7053, "lng": -73.9216, "address": "56 Bogart St", "city": "Brooklyn, NY"}
    ev_rooftop = await event("demo", "ev-neon-rooftop", "Neon Rooftop: Demo Artist Solo Show",
                             "One night only. 12 new neon pieces, a live paint wall, DJ set, and a very good rooftop. Ticket includes a signed print.",
                             "gallery_opening", {**BK, "address": "Rooftop, 45 Wyckoff Ave"}, ahead(days=3, hours=4), 5, "ev-neon-rooftop", cap=60, price=25.0)
    ev_battle = await event("demo", "ev-live-battle", "Live Painting Battle: Kai vs Dex",
                            "Two artists, two walls, 90 minutes. Crowd picks the winner. Tiny room — RSVP fast.",
                            "live_painting", BK, ahead(days=6, hours=2), 2, "ev-live-battle", cap=3)
    series_id = new_id()
    sketch_first = None
    for i in range(4):
        e = await event("kai", "ev-sketch-club", "Sunday Sketch Club", "Free weekly drawing session at the Bushwick studio. Coffee's on us, bring a pen. All levels.",
                        "meetup", BK, iso((NOW + timedelta(days=(6 - NOW.weekday()) % 7 or 7, weeks=i)).replace(hour=15, minute=0, second=0, microsecond=0)), 3, "ev-sketch-club",
                        series=(series_id, i + 1, 4), created=ago(days=10))
        sketch_first = sketch_first or e
    ev_tokyo = await event("yuki", "ev-tokyo-neon", "Tokyo Neon Night (Virtual Walkthrough)", "Live-streamed walkthrough of my new digital series with a Q&A. Link sent to attendees.",
                           "virtual", {"lat": 35.6938, "lng": 139.7034, "address": "Online", "city": "Tokyo, JP"}, ahead(days=9, hours=6), 1.5, "ev-tokyo-neon")
    ev_market = await event("marisol", "ev-print-market", "Roma Norte Print Market", "30 artists, prints under $200, tacos. Marisol's new watercolor series debuts here.",
                            "market", {"lat": 19.4194, "lng": -99.1625, "address": "Plaza Río de Janeiro", "city": "Mexico City, MX"}, ahead(days=12), 7, "ev-print-market", cap=300, price=10.0)
    ev_workshop = await event("amara", "ev-fig-workshop", "Figurative Painting Workshop", "A full day painting from a live model with Amara. Materials included. 12 easels only.",
                              "workshop", {"lat": 51.5416, "lng": -0.0765, "address": "Unit 4, Hackney Wick", "city": "London, UK"}, ahead(days=16, hours=1), 6, "ev-fig-workshop", cap=12, price=40.0)
    ev_past = await event("demo", "ev-open-studio", "Spring Open Studio", "Doors open, canvases everywhere, come hang.", "gallery_opening", BK, ago(days=14, hours=-4), 4, "ev-open-studio", created=ago(days=30))

    # rsvps — rooftop (trending: many recent)
    await rsvp(ev_rooftop, "collector", ago(hours=20), paid=25.0)
    for who, h in [("jordan", 30), ("priya", 26), ("luca", 12), ("kai", 40), ("amara", 8), ("dex", 5), ("ines", 2)]:
        await rsvp(ev_rooftop, who, ago(hours=h), paid=25.0)
    # battle — full + waitlist
    for who, d in [("jordan", 4), ("priya", 3), ("luca", 2)]:
        await rsvp(ev_battle, who, ago(days=d))
    for who, d in [("ines", 1), ("collector", 0.5)]:
        await db.event_waitlist.insert_one({"id": new_id(), "event_id": ev_battle["id"], "user_id": users[who]["id"], "user_name": users[who]["name"],
                                            "user_email": users[who]["email"], "notified": False, "created_at": ago(days=d), "seed": SEED})
    # sketch club + others
    await rsvp(sketch_first, "collector", ago(days=2))
    await rsvp(sketch_first, "luca", ago(days=1))
    await rsvp(ev_tokyo, "collector", ago(days=3))
    await rsvp(ev_tokyo, "jordan", ago(days=1))
    await rsvp(ev_market, "priya", ago(days=2), paid=10.0)
    for who in ["jordan", "priya", "luca"]:
        await rsvp(ev_workshop, who, ago(days=random.randint(1, 4)), paid=40.0)
    # past — checked-in
    await rsvp(ev_past, "collector", ago(days=20), checked_in=True)
    await rsvp(ev_past, "jordan", ago(days=19), checked_in=True)
    await rsvp(ev_past, "priya", ago(days=18))

    # --- messages
    A, C, J, AM = users["demo"], users["collector"], users["jordan"], users["amara"]
    msgs = [
        dm(C, A, "Hey! Just saw Midnight Bodega on the feed. Is it still available?", ago(days=1, hours=5)),
        dm(A, C, "It is! 36×48, oil. Here it is 👇", ago(days=1, hours=4, minutes=50), attachment={"kind": "artwork", "ref_id": ART["demo-midnight-bodega"]["id"]}),
        dm(C, A, "Stunning. I put in an offer at $2,000 — I know it's under, happy to talk.", ago(days=1, hours=4, minutes=30)),
        dm(A, C, "Saw it. Let me sleep on it — shipping to you would be ~$180 crated. Also, Biscuit's portrait update:", ago(days=1, hours=3)),
        dm(A, C, "Sketch is locked, blocking colour tonight.", ago(days=1, hours=2, minutes=58), attachment={"kind": "commission", "ref_id": c_progress["id"]}),
        dm(C, A, "He's going to look ridiculous in chrome. Perfect. See you at the rooftop show Friday 🎟️", ago(hours=22)),
        dm(A, C, "Ticket's on me next time. Chrome Heart auction ends in under an hour btw 👀", ago(minutes=35), read=False),
        dm(J, A, "Yo — pending commission request for the bar wall. 48×72, budget's flexible.", ago(hours=2)),
        dm(A, J, "Saw it, replying tonight. Love the space.", ago(hours=1, minutes=40)),
        dm(AM, C, "Your grandmother's portrait is delivered on the platform — take a look when you're ready. No rush.", ago(hours=23)),
        dm(C, AM, "Amara. I cried. Approving now.", ago(hours=21)),
    ]
    for m in msgs:
        await db.messages.insert_one(m)

    # --- notifications (protagonists)
    N = [
        # Demo Artist
        notif(A["id"], "offer_received", offer_id=of_pending["id"], artwork_id=ART["demo-midnight-bodega"]["id"], amount=2000.0, created_at=ago(hours=4)),
        notif(A["id"], "commission_request", commission_id=c_pending["id"], created_at=ago(hours=2)),
        notif(A["id"], "event_ticket_paid", event_id=ev_rooftop["id"], event_title=ev_rooftop["title"], from_user_id=C["id"], from_user_name=C["name"], amount=25.0, created_at=ago(hours=20)),
        notif(A["id"], "event_rsvp", event_id=ev_rooftop["id"], event_title=ev_rooftop["title"], from_user_id=users["dex"]["id"], from_user_name="Dex Morrow", created_at=ago(hours=5)),
        notif(A["id"], "new_follower", follower_id=users["luca"]["id"], created_at=ago(hours=7)),
        notif(A["id"], "artwork_sold", order_id=o_shipped["id"], artwork_id=ART["demo-wildstyle-01"]["id"], amount=640.0, read=True, created_at=ago(days=2)),
        notif(A["id"], "post_liked", post_id=POST_IDS[0]["id"], from_user_id=C["id"], from_user_name=C["name"], created_at=ago(hours=1)),
        notif(A["id"], "new_comment", artwork_id=ART["demo-neon-alley"]["id"], from_user_id=C["id"], from_user_name=C["name"], created_at=ago(days=3), read=True),
        notif(A["id"], "watched_auction_leader", auction_id=au_live_soon["id"], artwork_id=ART["demo-chrome-heart"]["id"], amount=600.0, created_at=ago(hours=1, minutes=10)),
        # Demo Collector
        notif(C["id"], "new_message", from_user_id=A["id"], from_user_name=A["name"], preview="Ticket's on me next time. Chrome Heart auction ends in under an hour btw 👀", created_at=ago(minutes=35)),
        notif(C["id"], "auction_ending", auction_id=au_live_soon["id"], artwork_id=ART["demo-chrome-heart"]["id"], current_bid=600.0, end_at=au_live_soon["end_at"], created_at=ago(minutes=18)),
        notif(C["id"], "outbid", auction_id=au_live_2["id"], artwork_id=ART["kai-throwie-gold"]["id"], amount=475.0, created_at=ago(hours=3)),
        notif(C["id"], "auction_won", auction_id=au_won["id"], artwork_id=ART["yuki-vending-machine"]["id"], amount=340.0, created_at=ago(hours=9)),
        notif(C["id"], "offer_counter", offer_id=of_countered["id"], artwork_id=ART["kai-rooftop-crew"]["id"], amount=1950.0, created_at=ago(hours=20)),
        notif(C["id"], "offer_accept", offer_id=of_accepted["id"], artwork_id=ART["dex-melting-mickey"]["id"], amount=1300.0, created_at=ago(days=1, hours=20), read=True),
        notif(C["id"], "commission_delivered", commission_id=c_delivered["id"], created_at=ago(days=1)),
        notif(C["id"], "commission_progress", commission_id=c_progress["id"], created_at=ago(days=2), read=True),
        notif(C["id"], "order_shipped", order_id=o_shipped["id"], carrier="USPS", tracking="9400111899223197428490", created_at=ago(days=1)),
        notif(C["id"], "event_ticket_paid", event_id=ev_rooftop["id"], event_title=ev_rooftop["title"], amount=25.0, read=True, created_at=ago(hours=20)),
        notif(C["id"], "event_reminder", event_id=sketch_first["id"], event_title="Sunday Sketch Club", created_at=ago(hours=6), read=True),
    ]
    for n in N:
        await db.notifications.insert_one(n)

    # settings: make Auntie Grace the featured piece
    await db.settings.update_one({"id": "global"}, {"$set": {"aotw_artwork_id": ART["amara-auntie"]["id"]}})
    log.info("✅ demo world seeded")


if __name__ == "__main__":
    asyncio.run(main())


async def refresh_demo_dates():
    """Keep the demo world evergreen: roll seeded upcoming events forward by whole weeks once they pass (series move together)."""
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    now = _dt.now(_tz.utc)
    moved = 0
    evs = await db.events.find({"seed": SEED, "cancelled": {"$ne": True}, "title": {"$not": {"$regex": "^Spring Open Studio"}}}).to_list(500)
    groups: dict = {}
    for e in evs:
        groups.setdefault(e.get("series_id") or e["id"], []).append(e)
    for members in groups.values():
        members.sort(key=lambda x: x["start_at"])
        first = _dt.fromisoformat(members[0]["start_at"])
        if first >= now:
            continue
        shift = _td(weeks=((now - first).days // 7) + 1)
        for e in members:
            patch = {"start_at": iso(_dt.fromisoformat(e["start_at"]) + shift)}
            if e.get("end_at"):
                patch["end_at"] = iso(_dt.fromisoformat(e["end_at"]) + shift)
            await db.events.update_one({"id": e["id"]}, {"$set": patch, "$unset": {"reminder_24h_sent": "", "reminder_1h_sent": ""}})
            moved += 1
    # re-space any series whose occurrences collided (7 days apart from the earliest)
    for sid in {e["series_id"] for e in evs if e.get("series_id")}:
        occ = sorted(await db.events.find({"series_id": sid}).to_list(50), key=lambda x: (x.get("series_seq") or 0))
        base = min(_dt.fromisoformat(o["start_at"]) for o in occ)
        for k, o in enumerate(occ):
            want = base + _td(weeks=k)
            if _dt.fromisoformat(o["start_at"]) != want:
                dur = _dt.fromisoformat(o["end_at"]) - _dt.fromisoformat(o["start_at"]) if o.get("end_at") else None
                await db.events.update_one({"id": o["id"]}, {"$set": {"start_at": iso(want), **({"end_at": iso(want + dur)} if dur else {})}})
    return moved
