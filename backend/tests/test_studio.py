"""Backend tests for Virtual Artist Studio (studio + posts) + light regression."""
import io
import os
import time
import pytest
import requests
from PIL import Image

BASE = os.environ.get("BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/") + "/api"

VALID_THEMES = {"urban_graffiti", "luxury_gallery", "darkroom", "industrial",
                "digital", "minimal", "warm_studio"}


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(f"{BASE}/auth/login", json={
        "email": "monster@houseofmonster.com", "password": os.environ["ADMIN_PASSWORD"]
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return d["token"], d["user"]["id"]


@pytest.fixture(scope="module")
def artist_token(session):
    ts = int(time.time())
    email = f"artist_studio_{ts}@test.com"
    r = session.post(f"{BASE}/auth/register", json={
        "email": email, "password": "Pass1234!", "name": "TEST_StudioArtist", "role": "artist"
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return d["token"], d["user"]["id"]


@pytest.fixture(scope="module")
def buyer_token(session):
    ts = int(time.time()) + 1
    email = f"buyer_studio_{ts}@test.com"
    r = session.post(f"{BASE}/auth/register", json={
        "email": email, "password": "Pass1234!", "name": "TEST_StudioBuyer", "role": "buyer"
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return d["token"], d["user"]["id"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- Themes ----------------
class TestThemes:
    def test_list_themes(self, session):
        r = session.get(f"{BASE}/studio/themes")
        assert r.status_code == 200
        themes = r.json()
        assert isinstance(themes, list)
        assert len(themes) == 7
        ids = {t["id"] for t in themes}
        assert ids == VALID_THEMES
        for t in themes:
            for k in ("id", "name", "bg_url", "accent", "secondary", "text", "surface", "vibe"):
                assert k in t, f"missing key {k} in theme {t.get('id')}"


# ---------------- Studio GET ----------------
class TestStudioGet:
    def test_get_studio_for_artist(self, session, artist_token):
        _, aid = artist_token
        r = session.get(f"{BASE}/studio/{aid}")
        assert r.status_code == 200, r.text
        d = r.json()
        for key in ("artist", "config", "artworks", "auctions", "posts", "social"):
            assert key in d
        assert d["artist"]["id"] == aid
        assert d["config"]["theme"] in VALID_THEMES
        assert "all" in d["artworks"] and "available" in d["artworks"]
        assert "sold" in d["artworks"] and "featured" in d["artworks"]
        assert "followers" in d["social"] and "following" in d["social"]

    def test_get_studio_increments_visits(self, session, artist_token):
        _, aid = artist_token
        r1 = session.get(f"{BASE}/studio/{aid}")
        v1 = r1.json()["config"].get("visits", 0)
        r2 = session.get(f"{BASE}/studio/{aid}")
        v2 = r2.json()["config"].get("visits", 0)
        assert v2 > v1, f"visits did not increment: {v1} -> {v2}"

    def test_get_studio_admin_works(self, session, admin_token):
        _, aid = admin_token
        r = session.get(f"{BASE}/studio/{aid}")
        assert r.status_code == 200, r.text
        assert r.json()["artist"]["id"] == aid

    def test_get_studio_nonexistent_404(self, session):
        r = session.get(f"{BASE}/studio/does-not-exist-xyz-123")
        assert r.status_code == 404

    def test_get_studio_buyer_id_404(self, session, buyer_token):
        # buyer's user id shouldn't have a studio (role filter excludes buyer)
        _, bid = buyer_token
        r = session.get(f"{BASE}/studio/{bid}")
        assert r.status_code == 404


# ---------------- Studio PATCH ----------------
class TestStudioPatch:
    def test_patch_studio_artist(self, session, artist_token):
        tok, aid = artist_token
        payload = {
            "theme": "darkroom",
            "accent_color": "#FF00AA",
            "lighting": {"preset": "spotlight", "intensity": 80},
            "typography": "mono",
            "artist_story": {"location": "Berlin", "style": "graffiti"},
        }
        r = session.patch(f"{BASE}/studio", json=payload, headers=auth_headers(tok))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["theme"] == "darkroom"
        assert d["accent_color"] == "#FF00AA"
        assert d["lighting"]["preset"] == "spotlight"
        assert d["typography"] == "mono"
        assert d["artist_story"]["location"] == "Berlin"

    def test_patch_sections(self, session, artist_token):
        tok, _ = artist_token
        sections = [
            {"id": "featured", "kind": "featured_works", "title": "The Walls", "order": 0, "visible": True},
            {"id": "story", "kind": "story", "title": "My Journey", "order": 1, "visible": True},
        ]
        r = session.patch(f"{BASE}/studio", json={"sections": sections}, headers=auth_headers(tok))
        assert r.status_code == 200, r.text
        assert r.json()["sections"][0]["title"] == "The Walls"

    def test_patch_buyer_403(self, session, buyer_token):
        tok, _ = buyer_token
        r = session.patch(f"{BASE}/studio", json={"theme": "digital"}, headers=auth_headers(tok))
        assert r.status_code == 403, r.text

    def test_patch_admin_ok(self, session, admin_token):
        tok, _ = admin_token
        r = session.patch(f"{BASE}/studio", json={"theme": "luxury_gallery"}, headers=auth_headers(tok))
        assert r.status_code == 200
        assert r.json()["theme"] == "luxury_gallery"

    def test_patch_no_auth_401(self, session):
        r = session.patch(f"{BASE}/studio", json={"theme": "digital"})
        assert r.status_code in (401, 403)


# ---------------- Analytics ----------------
class TestAnalytics:
    def test_analytics_artist(self, session, artist_token):
        tok, _ = artist_token
        r = session.get(f"{BASE}/studio/analytics/me", headers=auth_headers(tok))
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("visits", "total_likes", "total_comments", "followers",
                  "sales", "revenue", "artworks_count", "top_artworks"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["top_artworks"], list)

    def test_analytics_buyer_403(self, session, buyer_token):
        tok, _ = buyer_token
        r = session.get(f"{BASE}/studio/analytics/me", headers=auth_headers(tok))
        assert r.status_code == 403

    def test_analytics_admin_ok(self, session, admin_token):
        tok, _ = admin_token
        r = session.get(f"{BASE}/studio/analytics/me", headers=auth_headers(tok))
        assert r.status_code == 200


# ---------------- AI Designer ----------------
class TestAIDesigner:
    def test_ai_designer_buyer_403(self, session, buyer_token):
        tok, _ = buyer_token
        r = session.post(f"{BASE}/studio/ai-design",
                         json={"prompt": "test"}, headers=auth_headers(tok))
        assert r.status_code == 403

    def test_ai_designer_no_auth(self, session):
        r = session.post(f"{BASE}/studio/ai-design", json={"prompt": "test"})
        assert r.status_code in (401, 403)

    def test_ai_designer_artist_returns_config(self, session, artist_token):
        tok, _ = artist_token
        r = session.post(f"{BASE}/studio/ai-design",
                         json={"prompt": "cyberpunk digital gallery with cyan neon"},
                         headers=auth_headers(tok), timeout=60)
        # LLM may fail -> 500 is acceptable per spec
        if r.status_code == 500:
            pytest.skip(f"LLM call failed (acceptable): {r.text[:200]}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "prompt" in d and "config" in d
        cfg = d["config"]
        assert cfg.get("theme") in VALID_THEMES, f"invalid theme {cfg.get('theme')}"
        assert isinstance(cfg.get("accent_color"), str) and cfg["accent_color"].startswith("#")
        assert "lighting" in cfg and "preset" in cfg["lighting"] and "intensity" in cfg["lighting"]
        assert "typography" in cfg
        assert isinstance(cfg.get("section_titles"), dict)
        assert isinstance(cfg.get("story_hint"), str)


# ---------------- Posts ----------------
class TestPosts:
    @pytest.fixture(scope="class")
    def created_post(self, session, artist_token):
        tok, aid = artist_token
        r = session.post(f"{BASE}/posts", json={
            "kind": "update", "text": "TEST_post hello world"
        }, headers=auth_headers(tok))
        assert r.status_code == 200, r.text
        p = r.json()
        return p, tok, aid

    def test_create_post(self, created_post):
        p, _, aid = created_post
        assert p["id"] and p["artist_id"] == aid
        assert p["artist_name"]
        assert p["text"] == "TEST_post hello world"
        assert p["like_count"] == 0
        assert p["pinned"] is False

    def test_create_post_buyer_403(self, session, buyer_token):
        tok, _ = buyer_token
        r = session.post(f"{BASE}/posts", json={"kind": "update", "text": "nope"},
                         headers=auth_headers(tok))
        assert r.status_code == 403

    def test_list_posts(self, session, artist_token, created_post):
        _, aid = artist_token
        r = session.get(f"{BASE}/posts", params={"artist_id": aid})
        assert r.status_code == 200
        posts = r.json()
        assert isinstance(posts, list)
        assert any(p["id"] == created_post[0]["id"] for p in posts)

    def test_pin_toggle(self, session, created_post):
        p, tok, _ = created_post
        r = session.patch(f"{BASE}/posts/{p['id']}/pin",
                          json={"pinned": True}, headers=auth_headers(tok))
        assert r.status_code == 200
        assert r.json()["pinned"] is True
        # unpin
        r = session.patch(f"{BASE}/posts/{p['id']}/pin",
                          json={"pinned": False}, headers=auth_headers(tok))
        assert r.status_code == 200
        assert r.json()["pinned"] is False

    def test_list_posts_order_pinned_first(self, session, artist_token):
        tok, aid = artist_token
        # create two posts
        r1 = session.post(f"{BASE}/posts", json={"kind": "update", "text": "TEST_p1"}, headers=auth_headers(tok))
        r2 = session.post(f"{BASE}/posts", json={"kind": "update", "text": "TEST_p2"}, headers=auth_headers(tok))
        p2_id = r2.json()["id"]
        # pin the older one (p1) -- actually pin p2 which is newer, then unpin and pin p1
        # Simpler: create p3 and pin p3-first not needed; pin p2 and verify it comes first
        assert r1.status_code == 200 and r2.status_code == 200
        session.patch(f"{BASE}/posts/{p2_id}/pin", json={"pinned": True}, headers=auth_headers(tok))
        # create another unpinned newer post
        r3 = session.post(f"{BASE}/posts", json={"kind": "update", "text": "TEST_p3_newer"}, headers=auth_headers(tok))
        assert r3.status_code == 200
        listing = session.get(f"{BASE}/posts", params={"artist_id": aid}).json()
        assert listing[0]["id"] == p2_id, f"expected pinned post first, got {listing[0]['id']}"

    def test_like_unlike(self, session, buyer_token, created_post):
        p, _, _ = created_post
        btok, _ = buyer_token
        r = session.post(f"{BASE}/posts/{p['id']}/like", headers=auth_headers(btok))
        assert r.status_code == 200
        assert r.json()["liked"] is True
        # idempotent
        r = session.post(f"{BASE}/posts/{p['id']}/like", headers=auth_headers(btok))
        assert r.status_code == 200
        # verify count
        listing = session.get(f"{BASE}/posts", params={"artist_id": p["artist_id"]}).json()
        found = next(pp for pp in listing if pp["id"] == p["id"])
        assert found["like_count"] >= 1
        # unlike
        r = session.delete(f"{BASE}/posts/{p['id']}/like", headers=auth_headers(btok))
        assert r.status_code == 200
        assert r.json()["liked"] is False

    def test_delete_post_non_owner_403(self, session, buyer_token, created_post):
        p, _, _ = created_post
        btok, _ = buyer_token
        r = session.delete(f"{BASE}/posts/{p['id']}", headers=auth_headers(btok))
        assert r.status_code == 403

    def test_delete_post_owner_ok(self, session, artist_token):
        tok, _ = artist_token
        r = session.post(f"{BASE}/posts", json={"kind": "update", "text": "TEST_todelete"},
                         headers=auth_headers(tok))
        pid = r.json()["id"]
        r = session.delete(f"{BASE}/posts/{pid}", headers=auth_headers(tok))
        assert r.status_code == 200

    def test_delete_post_admin_ok(self, session, artist_token, admin_token):
        atok, _ = artist_token
        adtok, _ = admin_token
        r = session.post(f"{BASE}/posts", json={"kind": "update", "text": "TEST_admin_delete"},
                         headers=auth_headers(atok))
        pid = r.json()["id"]
        r = session.delete(f"{BASE}/posts/{pid}", headers=auth_headers(adtok))
        assert r.status_code == 200


# ---------------- Regression sweep ----------------
class TestRegression:
    def test_root(self, session):
        r = session.get(f"{BASE}/")
        assert r.status_code == 200

    def test_settings(self, session):
        r = session.get(f"{BASE}/settings")
        assert r.status_code == 200
        assert "commission_percent" in r.json()

    def test_artworks_list(self, session):
        r = session.get(f"{BASE}/artworks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_auth_me(self, session, admin_token):
        tok, _ = admin_token
        r = session.get(f"{BASE}/auth/me", headers=auth_headers(tok))
        assert r.status_code == 200

    def test_admin_stats(self, session, admin_token):
        tok, _ = admin_token
        r = session.get(f"{BASE}/admin/stats", headers=auth_headers(tok))
        assert r.status_code == 200

    def test_artist_dashboard(self, session, artist_token):
        tok, _ = artist_token
        r = session.get(f"{BASE}/artist/dashboard", headers=auth_headers(tok))
        assert r.status_code == 200

    def test_feed(self, session):
        r = session.get(f"{BASE}/feed")
        assert r.status_code in (200, 404)  # feed may not exist depending on route

    def test_rankings(self, session):
        r = session.get(f"{BASE}/rankings/leaderboard")
        assert r.status_code in (200, 404)

    def test_search(self, session):
        r = session.get(f"{BASE}/search", params={"q": "art"})
        assert r.status_code in (200, 404, 422)
