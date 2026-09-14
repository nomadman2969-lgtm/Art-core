"""Backend tests for the NEW Studio (themes/textures/draft-publish/sections/featured/
commission_open) + Stripe Connect endpoints. Also validates commission progress[] used
by the CommissionTimeline UI.

Run:
    cd /app && python -m pytest backend/tests/test_new_studio_connect.py -v -n 0 \
        --junitxml=/app/test_reports/pytest/new_studio_connect.xml
"""
import io
import os
import time
import uuid
import pytest
import requests
from PIL import Image
from pymongo import MongoClient

BASE = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://monster-curated.preview.emergentagent.com",
).rstrip("/") + "/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "house_of_monster")

mc = MongoClient(MONGO_URL)
sync_db = mc[DB_NAME]

NEW_THEMES = {"urban_graffiti", "luxury_gallery", "dark_gallery",
              "industrial", "neon_digital", "minimal", "custom"}
TEXTURES = {"none", "graffiti", "brick", "concrete", "grid", "noise", "paper"}
LAYOUTS = {"grid", "masonry", "salon", "showcase", "carousel"}


def _req(method, path, token=None, **kw):
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{BASE}{path}", headers=headers, timeout=30, **kw)


def _register(role, tag):
    ts = int(time.time() * 1000)
    email = f"TEST_{tag}_{ts}_{uuid.uuid4().hex[:5]}@test.com"
    r = _req("POST", "/auth/register", json={
        "email": email, "password": "Pass1234!",
        "name": f"{tag.title()} {ts}", "role": role,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _make_live_artwork(artist_token, price=200.0, title="TEST piece"):
    img = Image.new("RGB", (60, 60), (100, 100, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    r = _req("POST", "/upload/image", token=artist_token,
             files={"file": ("t.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 200, r.text
    ip = r.json()["path"]
    r = _req("POST", "/artworks", token=artist_token, json={
        "title": title, "description": "d", "price": price,
        "medium": "painting", "images": [ip],
        "width_in": 10, "height_in": 10, "year": 2026,
    })
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    sync_db.artworks.update_one({"id": aid}, {"$set": {"status": "live"}})
    return aid


@pytest.fixture(scope="module")
def ctx():
    r = _req("POST", "/auth/login", json={
        "email": "monster@houseofmonster.com", "password": os.environ["ADMIN_PASSWORD"]
    })
    assert r.status_code == 200, r.text
    admin_token = r.json()["token"]
    _req("PATCH", "/admin/settings", token=admin_token, json={"upload_fee": 0})
    artist = _register("artist", "studio_artist")
    buyer = _register("buyer", "studio_buyer")
    return {"admin_token": admin_token, "artist": artist, "buyer": buyer}


# ============================================================
# STUDIO: THEMES
# ============================================================
class TestNewThemes:
    def test_list_returns_seven_new_themes(self, ctx):
        r = _req("GET", "/studio/themes")
        assert r.status_code == 200
        themes = r.json()
        assert isinstance(themes, list) and len(themes) == 7
        ids = {t["id"] for t in themes}
        assert ids == NEW_THEMES, f"Expected {NEW_THEMES}, got {ids}"
        for t in themes:
            for k in ("id", "name", "accent", "secondary", "text", "surface", "vibe"):
                assert k in t

    def test_patch_all_seven_themes(self, ctx):
        tok = ctx["artist"]["token"]
        for tid in NEW_THEMES:
            r = _req("PATCH", "/studio", token=tok, json={"theme": tid, "publish": True})
            assert r.status_code == 200, r.text
            assert r.json()["theme"] == tid

    def test_patch_invalid_theme_400(self, ctx):
        tok = ctx["artist"]["token"]
        r = _req("PATCH", "/studio", token=tok, json={"theme": "not_a_theme", "publish": True})
        assert r.status_code == 400

    def test_legacy_alias_migrates(self, ctx):
        """Legacy 'darkroom' should be accepted and stored as 'dark_gallery'."""
        tok = ctx["artist"]["token"]
        r = _req("PATCH", "/studio", token=tok, json={"theme": "darkroom", "publish": True})
        assert r.status_code == 200
        assert r.json()["theme"] == "dark_gallery"
        # digital -> neon_digital
        r = _req("PATCH", "/studio", token=tok, json={"theme": "digital", "publish": True})
        assert r.json()["theme"] == "neon_digital"
        # warm_studio -> industrial
        r = _req("PATCH", "/studio", token=tok, json={"theme": "warm_studio", "publish": True})
        assert r.json()["theme"] == "industrial"


# ============================================================
# STUDIO: TEXTURES
# ============================================================
class TestTextures:
    def test_patch_each_texture(self, ctx):
        tok = ctx["artist"]["token"]
        for tex in TEXTURES:
            r = _req("PATCH", "/studio", token=tok, json={
                "background": {"type": "theme", "texture": tex, "texture_opacity": 50},
                "publish": True,
            })
            assert r.status_code == 200, f"texture={tex}: {r.text}"
            bg = r.json()["background"]
            assert bg["texture"] == tex
            assert bg["texture_opacity"] == 50

    def test_invalid_texture_400(self, ctx):
        tok = ctx["artist"]["token"]
        r = _req("PATCH", "/studio", token=tok, json={
            "background": {"type": "theme", "texture": "lava"},
            "publish": True,
        })
        assert r.status_code == 400

    def test_studio_get_returns_texture(self, ctx):
        tok = ctx["artist"]["token"]
        aid = ctx["artist"]["user"]["id"]
        _req("PATCH", "/studio", token=tok, json={
            "background": {"type": "theme", "texture": "brick", "texture_opacity": 40},
            "publish": True,
        })
        r = _req("GET", f"/studio/{aid}")
        assert r.status_code == 200
        assert r.json()["config"]["background"]["texture"] == "brick"


# ============================================================
# STUDIO: DRAFT / PUBLISH / DISCARD
# ============================================================
class TestDraftPublish:
    def test_draft_write_then_publish(self, ctx):
        tok = ctx["artist"]["token"]
        aid = ctx["artist"]["user"]["id"]
        # Publish a known baseline first
        _req("PATCH", "/studio", token=tok, json={"theme": "minimal", "publish": True})
        # Now write a draft (theme change)
        r = _req("PATCH", "/studio", token=tok, json={"theme": "industrial"})
        assert r.status_code == 200
        cfg = r.json()
        assert cfg["theme"] == "minimal", "Published theme should NOT change on draft write"
        assert cfg.get("draft") is not None
        assert cfg["draft"].get("theme") == "industrial"

        # Public GET (no preview) still shows minimal
        pub = _req("GET", f"/studio/{aid}").json()
        assert pub["config"]["theme"] == "minimal"
        assert pub["config"]["has_draft"] is True
        assert pub["config"]["is_preview"] is False

        # Owner preview shows industrial
        prev = _req("GET", f"/studio/{aid}?preview=true", token=tok).json()
        assert prev["config"]["theme"] == "industrial"
        assert prev["config"]["is_preview"] is True

        # Publish
        r = _req("POST", "/studio/publish", token=tok)
        assert r.status_code == 200
        assert r.json()["theme"] == "industrial"
        assert r.json().get("draft") is None

        # Public now shows industrial
        pub = _req("GET", f"/studio/{aid}").json()
        assert pub["config"]["theme"] == "industrial"
        assert pub["config"]["has_draft"] is False

    def test_publish_without_draft_400(self, ctx):
        tok = ctx["artist"]["token"]
        # Ensure no draft
        _req("POST", "/studio/discard-draft", token=tok)
        r = _req("POST", "/studio/publish", token=tok)
        assert r.status_code == 400

    def test_discard_draft(self, ctx):
        tok = ctx["artist"]["token"]
        # Write draft
        _req("PATCH", "/studio", token=tok, json={"theme": "neon_digital"})
        # Discard
        r = _req("POST", "/studio/discard-draft", token=tok)
        assert r.status_code == 200
        assert r.json().get("draft") is None

    def test_preview_by_non_owner_ignored(self, ctx):
        """Non-owner asking for preview should get published, not draft."""
        artist_tok = ctx["artist"]["token"]
        aid = ctx["artist"]["user"]["id"]
        _req("PATCH", "/studio", token=artist_tok, json={"theme": "luxury_gallery", "publish": True})
        _req("PATCH", "/studio", token=artist_tok, json={"theme": "neon_digital"})  # draft
        # Buyer preview attempt
        r = _req("GET", f"/studio/{aid}?preview=true", token=ctx["buyer"]["token"])
        assert r.status_code == 200
        assert r.json()["config"]["theme"] == "luxury_gallery"
        assert r.json()["config"]["is_preview"] is False


# ============================================================
# STUDIO: SECTIONS - new rich kinds + layout picker
# ============================================================
class TestSectionsRich:
    def test_all_section_kinds_accepted(self, ctx):
        tok = ctx["artist"]["token"]
        sections = [
            {"id": "s1", "kind": "featured_works", "title": "Featured", "order": 0, "visible": True, "layout": "salon"},
            {"id": "s2", "kind": "available_now", "title": "Live", "order": 1, "visible": True, "layout": "masonry"},
            {"id": "s3", "kind": "sold_works", "title": "Sold", "order": 2, "visible": True, "layout": "showcase"},
            {"id": "s4", "kind": "upcoming_auctions", "title": "Auctions", "order": 3, "visible": True},
            {"id": "s5", "kind": "feed", "title": "Feed", "order": 4, "visible": True},
            {"id": "s6", "kind": "story", "title": "Story", "order": 5, "visible": True},
            {"id": "s7", "kind": "commission", "title": "Commissions", "order": 6, "visible": True},
            {"id": "s8", "kind": "announcement", "title": "News", "order": 7, "visible": True,
             "body": "Big drop soon!", "variant": "warning"},
            {"id": "s9", "kind": "text_block", "title": "About", "order": 8, "visible": True,
             "body": "Hello world"},
            {"id": "s10", "kind": "button_cta", "title": "Shop", "order": 9, "visible": True,
             "button_text": "Buy Now", "button_link": "https://example.com"},
            {"id": "s11", "kind": "image_block", "title": "Poster", "order": 10, "visible": True,
             "image": "/tmp/poster.jpg", "caption": "poster caption"},
            {"id": "s12", "kind": "custom", "title": "Custom", "order": 11, "visible": True,
             "body": "custom body"},
        ]
        r = _req("PATCH", "/studio", token=tok, json={"sections": sections, "publish": True})
        assert r.status_code == 200, r.text
        saved = r.json()["sections"]
        kinds = {s["kind"] for s in saved}
        expected_kinds = {"featured_works", "available_now", "sold_works", "upcoming_auctions",
                          "feed", "story", "commission", "announcement", "text_block",
                          "button_cta", "image_block", "custom"}
        assert kinds == expected_kinds
        by_kind = {s["kind"]: s for s in saved}
        # Layout persistence
        assert by_kind["featured_works"]["layout"] == "salon"
        assert by_kind["available_now"]["layout"] == "masonry"
        assert by_kind["sold_works"]["layout"] == "showcase"
        # Rich payloads
        ann = by_kind["announcement"]
        assert ann["body"] == "Big drop soon!"
        assert ann["variant"] == "warning"
        btn = by_kind["button_cta"]
        assert btn["button_text"] == "Buy Now"
        assert btn["button_link"] == "https://example.com"
        img = by_kind["image_block"]
        assert img["image"] == "/tmp/poster.jpg"
        assert img["caption"] == "poster caption"

    def test_invalid_section_kind_400(self, ctx):
        tok = ctx["artist"]["token"]
        r = _req("PATCH", "/studio", token=tok, json={
            "sections": [{"id": "x", "kind": "not_a_kind", "title": "X", "order": 0, "visible": True}],
            "publish": True,
        })
        assert r.status_code == 400

    def test_invalid_layout_falls_back_to_grid(self, ctx):
        tok = ctx["artist"]["token"]
        r = _req("PATCH", "/studio", token=tok, json={
            "sections": [{"id": "f", "kind": "featured_works", "title": "F", "order": 0,
                          "visible": True, "layout": "hologram"}],
            "publish": True,
        })
        assert r.status_code == 200
        assert r.json()["sections"][0]["layout"] == "grid"


# ============================================================
# STUDIO: FEATURED PICKER + COMMISSION AVAILABILITY
# ============================================================
class TestFeaturedAndCommissionFlags:
    def test_featured_artwork_ids_persist_order(self, ctx):
        tok = ctx["artist"]["token"]
        aid_a = _make_live_artwork(tok, price=100, title="A")
        aid_b = _make_live_artwork(tok, price=100, title="B")
        aid_c = _make_live_artwork(tok, price=100, title="C")
        r = _req("PATCH", "/studio", token=tok, json={
            "featured_artwork_ids": [aid_c, aid_a, aid_b], "publish": True,
        })
        assert r.status_code == 200
        assert r.json()["featured_artwork_ids"] == [aid_c, aid_a, aid_b]

        # Public GET returns featured artworks in that same order
        r = _req("GET", f"/studio/{ctx['artist']['user']['id']}")
        assert r.status_code == 200
        featured = r.json()["artworks"]["featured"]
        ids = [a["id"] for a in featured]
        assert ids == [aid_c, aid_a, aid_b]

    def test_commission_open_toggle(self, ctx):
        tok = ctx["artist"]["token"]
        aid = ctx["artist"]["user"]["id"]
        r = _req("PATCH", "/studio", token=tok, json={
            "commission_open": False, "commission_blurb": "Booked till 2027", "publish": True,
        })
        assert r.status_code == 200
        assert r.json()["commission_open"] is False
        assert r.json()["commission_blurb"] == "Booked till 2027"
        pub = _req("GET", f"/studio/{aid}").json()
        assert pub["config"]["commission_open"] is False
        assert pub["config"]["commission_blurb"] == "Booked till 2027"


# ============================================================
# STRIPE CONNECT ENDPOINTS
# ============================================================
class TestConnect:
    def test_status_fresh_artist(self, ctx):
        tok = ctx["artist"]["token"]
        r = _req("GET", "/connect/status", token=tok)
        assert r.status_code == 200
        d = r.json()
        # Fresh artist has no stripe_account_id
        # If a previous test created it, connected may be true — accept either
        # but charges_enabled + payouts_enabled should be false in fresh sandbox
        assert d["charges_enabled"] is False
        assert d["payouts_enabled"] is False

    def test_onboarding_link_graceful(self, ctx):
        tok = ctx["artist"]["token"]
        r = _req("POST", "/connect/onboarding-link", token=tok, json={
            "return_url": "https://x.test/return",
        })
        # Either a URL (Connect enabled in sandbox) OR 400 with graceful message
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            assert r.json()["url"].startswith("https://")
        else:
            body = r.text.lower()
            assert "connect" in body or "stripe" in body

    def test_buyer_cannot_call_onboarding(self, ctx):
        tok = ctx["buyer"]["token"]
        r = _req("POST", "/connect/onboarding-link", token=tok, json={
            "return_url": "https://x.test/return",
        })
        assert r.status_code == 403

    def test_dashboard_link_no_account_400(self, ctx):
        """Dashboard link needs stripe_account_id — buyer has none."""
        tok = ctx["buyer"]["token"]
        r = _req("POST", "/connect/dashboard-link", token=tok)
        assert r.status_code == 400

    def test_payments_offer_pay_works_without_connect(self, ctx):
        """When seller has no connected Stripe account, offer payment still works
        (no transfer_data, funds land on platform). Graceful fallback."""
        artist_tok = ctx["artist"]["token"]
        # Ensure artist has no active connect account for this test
        sync_db.users.update_one(
            {"id": ctx["artist"]["user"]["id"]},
            {"$set": {"stripe_charges_enabled": False}}
        )
        aid = _make_live_artwork(artist_tok, price=200, title="Connect fallback")
        r = _req("POST", "/offers", token=ctx["buyer"]["token"],
                 json={"artwork_id": aid, "amount": 150})
        assert r.status_code == 200, r.text
        oid = r.json()["id"]
        r = _req("POST", f"/offers/{oid}/respond", token=artist_tok,
                 json={"action": "accept"})
        assert r.status_code == 200
        r = _req("POST", f"/payments/offers/{oid}/pay",
                 token=ctx["buyer"]["token"], json={"origin_url": "https://x.test"})
        assert r.status_code == 200, r.text
        assert r.json()["checkout_url"].startswith("https://")


# ============================================================
# COMMISSIONS: progress[] history feeds Timeline UI
# ============================================================
class TestCommissionTimelineData:
    def test_progress_array_populated_through_flow(self, ctx):
        artist_tok = ctx["artist"]["token"]
        buyer_tok = ctx["buyer"]["token"]
        artist_id = ctx["artist"]["user"]["id"]
        # Create
        r = _req("POST", "/commissions", token=buyer_tok, json={
            "artist_id": artist_id, "subject": "Timeline test",
            "budget": 200, "instructions": "please",
        })
        assert r.status_code == 200
        cid = r.json()["id"]

        # Artist counter
        r = _req("POST", f"/commissions/{cid}/respond", token=artist_tok,
                 json={"action": "counter", "counter_amount": 250})
        assert r.status_code == 200

        # Buyer accepts counter → in_progress
        r = _req("POST", f"/commissions/{cid}/buyer-action", token=buyer_tok,
                 json={"action": "accept_counter"})
        assert r.status_code == 200 and r.json()["status"] == "in_progress"

        # Progress update
        r = _req("POST", f"/commissions/{cid}/progress", token=artist_tok,
                 json={"message": "sketch stage", "image": "s.jpg"})
        assert r.status_code == 200
        c = r.json()
        # progress[] should now have >= 1 entry
        assert isinstance(c.get("progress"), list) and len(c["progress"]) >= 1
        entry = c["progress"][-1]
        assert entry.get("message") == "sketch stage"

    def test_get_commission_returns_all_fields_for_timeline(self, ctx):
        """The UI needs artist, buyer, status, counter_amount, progress, final_images fields."""
        artist_tok = ctx["artist"]["token"]
        buyer_tok = ctx["buyer"]["token"]
        artist_id = ctx["artist"]["user"]["id"]
        r = _req("POST", "/commissions", token=buyer_tok, json={
            "artist_id": artist_id, "subject": "Fields test",
            "budget": 100, "instructions": "hi",
        })
        cid = r.json()["id"]
        r = _req("GET", f"/commissions/{cid}", token=buyer_tok)
        assert r.status_code == 200
        c = r.json()
        for k in ("id", "status", "buyer", "artist", "budget", "progress", "final_images"):
            assert k in c, f"missing {k}"
