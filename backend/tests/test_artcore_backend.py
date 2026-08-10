"""Art Core backend regression + new social/messaging/search/feed tests."""
import io
import os
import time
import uuid
import pytest
import requests
from PIL import Image

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/") + "/api"
TS = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"

ADMIN_EMAIL = "monster@houseofmonster.com"
ADMIN_PASS = "MonsterAdmin2026!"

STATE = {}  # shared across tests


def _req(method, path, token=None, **kw):
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{BASE}{path}", headers=headers, timeout=30, **kw)


# ---- Fixtures / bootstrap ----
@pytest.fixture(scope="module", autouse=True)
def bootstrap():
    # Admin login
    r = _req("POST", "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    STATE["admin_token"] = r.json()["token"]
    STATE["admin_id"] = r.json()["user"]["id"]
    assert r.json()["user"]["role"] == "admin"

    # Register buyer
    STATE["buyer_email"] = f"TEST_buyer_{TS}@test.com"
    r = _req("POST", "/auth/register", json={
        "email": STATE["buyer_email"], "password": "Pass1234!",
        "name": "TEST Buyer", "role": "buyer"})
    assert r.status_code == 200, r.text
    STATE["buyer_token"] = r.json()["token"]
    STATE["buyer_id"] = r.json()["user"]["id"]

    # Register artist
    STATE["artist_email"] = f"TEST_artist_{TS}@test.com"
    r = _req("POST", "/auth/register", json={
        "email": STATE["artist_email"], "password": "Pass1234!",
        "name": "TEST Artist", "role": "artist"})
    assert r.status_code == 200, r.text
    STATE["artist_token"] = r.json()["token"]
    STATE["artist_id"] = r.json()["user"]["id"]

    # Second artist for messaging test
    STATE["artist2_email"] = f"TEST_artist2_{TS}@test.com"
    r = _req("POST", "/auth/register", json={
        "email": STATE["artist2_email"], "password": "Pass1234!",
        "name": "TEST Artist2", "role": "artist"})
    assert r.status_code == 200, r.text
    STATE["artist2_token"] = r.json()["token"]
    STATE["artist2_id"] = r.json()["user"]["id"]

    yield


# ---- Basics ----
class TestBasics:
    def test_root_app_name(self):
        r = _req("GET", "/")
        assert r.status_code == 200
        assert r.json().get("app") == "Art Core"

    def test_public_settings(self):
        r = _req("GET", "/settings")
        assert r.status_code == 200
        d = r.json()
        for f in ("commission_percent", "upload_fee", "currency"):
            assert f in d


# ---- Auth ----
class TestAuth:
    def test_get_me_buyer(self):
        r = _req("GET", "/auth/me", token=STATE["buyer_token"])
        assert r.status_code == 200
        assert r.json()["email"] == STATE["buyer_email"].lower()
        assert r.json()["role"] == "buyer"

    def test_patch_me_bio(self):
        r = _req("PATCH", "/auth/me", token=STATE["artist_token"], json={"bio": "I make neon art"})
        assert r.status_code == 200
        assert r.json()["bio"] == "I make neon art"

    def test_admin_role(self):
        r = _req("GET", "/auth/me", token=STATE["admin_token"])
        assert r.status_code == 200
        assert r.json()["role"] == "admin"


# ---- Role guards ----
class TestRoleGuards:
    def test_buyer_cannot_post_artwork(self):
        payload = {
            "title": "x", "description": "y", "medium": "painting",
            "width_in": 10, "height_in": 10, "price": 1.0, "images": ["dummy.jpg"],
        }
        r = _req("POST", "/artworks", token=STATE["buyer_token"], json=payload)
        assert r.status_code in (401, 403), r.text

    def test_artist_cannot_get_admin_stats(self):
        r = _req("GET", "/admin/stats", token=STATE["artist_token"])
        assert r.status_code == 403

    def test_non_admin_cannot_patch_settings(self):
        r = _req("PATCH", "/admin/settings", token=STATE["buyer_token"], json={"upload_fee": 0})
        assert r.status_code == 403


# ---- Upload + files ----
class TestUploads:
    def test_upload_and_fetch_image(self):
        img = Image.new("RGB", (200, 200), (200, 50, 100))
        buf = io.BytesIO(); img.save(buf, format="JPEG"); buf.seek(0)
        files = {"file": ("test.jpg", buf.getvalue(), "image/jpeg")}
        r = _req("POST", "/upload/image", token=STATE["artist_token"], files=files)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "path" in j and "url" in j
        STATE["image_path"] = j["path"]

        r2 = requests.get(f"{BASE}/files/{j['path']}", timeout=30)
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("image")


# ---- Artwork create + payments ----
class TestArtworkAndPayments:
    def _payload(self):
        return {
            "title": f"TEST Magenta {TS}",
            "description": "Test artwork",
            "medium": "painting",
            "style": "abstract",
            "color": "magenta",
            "width_in": 24.0,
            "height_in": 36.0,
            "price": 250.0,
            "images": [STATE.get("image_path", "dummy.jpg")],
        }

    def test_admin_set_upload_fee_zero(self):
        r = _req("PATCH", "/admin/settings", token=STATE["admin_token"], json={"upload_fee": 0})
        assert r.status_code == 200

    def test_create_artwork_with_fee_zero_goes_live(self):
        # Create artwork (always starts pending_fee) then call /payments/upload-fee
        # With fee=0 this should return {free:true} and flip status to live.
        r = _req("POST", "/artworks", token=STATE["artist_token"], json=self._payload())
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pending_fee"
        STATE["art_id_live"] = d["id"]

        r2 = _req("POST", "/payments/upload-fee", token=STATE["artist_token"],
                  json={"artwork_id": d["id"],
                        "origin_url": "https://monster-curated.preview.emergentagent.com"})
        assert r2.status_code == 200, r2.text
        assert r2.json().get("free") is True

        # Verify status flipped to live
        r3 = _req("GET", f"/artworks/{d['id']}")
        assert r3.status_code == 200
        assert r3.json()["status"] == "live"

    def test_upload_fee_free_endpoint_rejects_already_live(self):
        # Already live artwork -> upload-fee should 400
        r = _req("POST", "/payments/upload-fee", token=STATE["artist_token"],
                 json={"artwork_id": STATE["art_id_live"],
                       "origin_url": "https://monster-curated.preview.emergentagent.com"})
        assert r.status_code == 400

    def test_restore_fee_and_create_pending(self):
        r = _req("PATCH", "/admin/settings", token=STATE["admin_token"], json={"upload_fee": 5.0})
        assert r.status_code == 200
        r = _req("POST", "/artworks", token=STATE["artist_token"], json=self._payload())
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending_fee"
        STATE["art_id_pending"] = r.json()["id"]

    def test_upload_fee_stripe_checkout(self):
        r = _req("POST", "/payments/upload-fee", token=STATE["artist_token"],
                 json={"artwork_id": STATE["art_id_pending"],
                       "origin_url": "https://monster-curated.preview.emergentagent.com"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert "checkout_url" in j and j["checkout_url"].startswith("http")

    def test_buyer_checkout_returns_url(self):
        r = _req("POST", "/payments/checkout", token=STATE["buyer_token"],
                 json={"items": [{"artwork_id": STATE["art_id_live"], "quantity": 1}],
                       "shipping": {"name": "Buyer T", "address_line1": "123 St",
                                    "city": "NY", "state": "NY", "postal_code": "10001",
                                    "country": "US"},
                       "origin_url": "https://monster-curated.preview.emergentagent.com"})
        assert r.status_code == 200, r.text
        assert "checkout_url" in r.json()

    def test_fake_session_returns_404(self):
        r = _req("GET", "/payments/status/cs_test_fake_nonexistent_12345", token=STATE["buyer_token"])
        assert r.status_code == 404

    def test_get_artwork_by_id_includes_artist(self):
        r = _req("GET", f"/artworks/{STATE['art_id_live']}")
        assert r.status_code == 200
        assert r.json()["id"] == STATE["art_id_live"]
        assert "artist" in r.json()


# ---- AOTW / featured ----
class TestAOTW:
    def test_submit_aotw_artist(self):
        r = _req("POST", f"/artworks/{STATE['art_id_live']}/submit-aotw", token=STATE["artist_token"])
        assert r.status_code == 200, r.text

    def test_admin_list_submissions(self):
        r = _req("GET", "/admin/aotw/submissions", token=STATE["admin_token"])
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert any(a["id"] == STATE["art_id_live"] for a in r.json())

    def test_admin_set_aotw(self):
        r = _req("POST", "/admin/aotw", token=STATE["admin_token"],
                 json={"artwork_id": STATE["art_id_live"]})
        assert r.status_code == 200

    def test_get_aotw_returns_it(self):
        r = _req("GET", "/artworks/aotw")
        assert r.status_code == 200
        assert r.json() and r.json()["id"] == STATE["art_id_live"]

    def test_admin_featured_toggle(self):
        r = _req("POST", "/admin/featured", token=STATE["admin_token"],
                 json={"artwork_id": STATE["art_id_live"], "featured": True})
        assert r.status_code == 200


# ---- Admin / mentorship / newsletter ----
class TestAdmin:
    def test_admin_stats(self):
        r = _req("GET", "/admin/stats", token=STATE["admin_token"])
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_admin_orders(self):
        r = _req("GET", "/admin/orders", token=STATE["admin_token"])
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_list_artists(self):
        r = _req("GET", "/admin/artists", token=STATE["admin_token"])
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_mentorship_flow(self):
        r = _req("POST", "/admin/mentorship", token=STATE["admin_token"],
                 json={"artist_id": STATE["artist_id"], "note": "Great work"})
        assert r.status_code == 200, r.text
        mid = r.json()["id"]
        assert r.json()["resolved"] is False

        r = _req("GET", "/admin/mentorship", token=STATE["admin_token"])
        assert r.status_code == 200
        assert any(m["id"] == mid for m in r.json())

        r = _req("PATCH", f"/admin/mentorship/{mid}/resolve", token=STATE["admin_token"])
        assert r.status_code == 200

    def test_newsletter_signup(self):
        r = _req("POST", "/newsletter", json={"email": f"TEST_news_{TS}@test.com"})
        assert r.status_code in (200, 201)
        assert r.json().get("ok") is True


# ---- Artist dashboard + connect ----
class TestArtist:
    def test_artist_dashboard(self):
        r = _req("GET", "/artist/dashboard", token=STATE["artist_token"])
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_connect_start(self):
        r = _req("POST", "/artist/connect/start", token=STATE["artist_token"])
        assert r.status_code == 200
        assert "onboarding_url" in r.json()

    def test_connect_complete(self):
        r = _req("POST", "/artist/connect/complete", token=STATE["artist_token"])
        assert r.status_code == 200
        # verify status
        r2 = _req("GET", "/artist/dashboard", token=STATE["artist_token"])
        assert r2.status_code == 200


# ---- NEW: Social - follows ----
class TestFollows:
    def test_follow_artist(self):
        r = _req("POST", f"/users/{STATE['artist_id']}/follow", token=STATE["buyer_token"])
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

    def test_social_counts(self):
        r = _req("GET", f"/users/{STATE['artist_id']}/social", token=STATE["buyer_token"])
        assert r.status_code == 200
        d = r.json()
        assert d["followers"] >= 1
        assert d["is_following"] is True

    def test_social_no_auth_is_following_false(self):
        r = _req("GET", f"/users/{STATE['artist_id']}/social")
        assert r.status_code == 200
        assert r.json()["is_following"] is False

    def test_cannot_follow_self(self):
        r = _req("POST", f"/users/{STATE['buyer_id']}/follow", token=STATE["buyer_token"])
        assert r.status_code == 400

    def test_unfollow(self):
        r = _req("DELETE", f"/users/{STATE['artist_id']}/follow", token=STATE["buyer_token"])
        assert r.status_code == 200
        r2 = _req("GET", f"/users/{STATE['artist_id']}/social", token=STATE["buyer_token"])
        assert r2.json()["is_following"] is False


# ---- NEW: Likes ----
class TestLikes:
    def test_like_artwork(self):
        r = _req("POST", f"/artworks/{STATE['art_id_live']}/like", token=STATE["buyer_token"])
        assert r.status_code == 200
        assert r.json()["liked"] is True

    def test_get_likes_count(self):
        r = _req("GET", f"/artworks/{STATE['art_id_live']}/likes", token=STATE["buyer_token"])
        assert r.status_code == 200
        d = r.json()
        assert d["count"] >= 1
        assert d["liked"] is True

    def test_unlike(self):
        r = _req("DELETE", f"/artworks/{STATE['art_id_live']}/like", token=STATE["buyer_token"])
        assert r.status_code == 200
        assert r.json()["liked"] is False
        r2 = _req("GET", f"/artworks/{STATE['art_id_live']}/likes", token=STATE["buyer_token"])
        assert r2.json()["liked"] is False


# ---- NEW: Comments ----
class TestComments:
    def test_add_comment(self):
        r = _req("POST", f"/artworks/{STATE['art_id_live']}/comments",
                 token=STATE["buyer_token"], json={"text": "TEST amazing work"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["text"] == "TEST amazing work"
        STATE["comment_id"] = d["id"]

    def test_list_comments(self):
        r = _req("GET", f"/artworks/{STATE['art_id_live']}/comments")
        assert r.status_code == 200
        assert any(c["id"] == STATE["comment_id"] for c in r.json())

    def test_other_user_cannot_delete(self):
        r = _req("DELETE", f"/comments/{STATE['comment_id']}", token=STATE["artist_token"])
        assert r.status_code == 403

    def test_owner_can_delete(self):
        r = _req("DELETE", f"/comments/{STATE['comment_id']}", token=STATE["buyer_token"])
        assert r.status_code == 200
        r2 = _req("GET", f"/artworks/{STATE['art_id_live']}/comments")
        assert not any(c["id"] == STATE["comment_id"] for c in r2.json())


# ---- NEW: Messaging ----
class TestMessaging:
    def test_send_message_a_to_b(self):
        r = _req("POST", "/messages", token=STATE["artist_token"],
                 json={"to_user_id": STATE["artist2_id"], "text": "Hi from A"})
        assert r.status_code == 200, r.text

    def test_send_message_b_to_a(self):
        r = _req("POST", "/messages", token=STATE["artist2_token"],
                 json={"to_user_id": STATE["artist_id"], "text": "Hi back from B"})
        assert r.status_code == 200

    def test_cannot_send_to_self(self):
        r = _req("POST", "/messages", token=STATE["artist_token"],
                 json={"to_user_id": STATE["artist_id"], "text": "self"})
        assert r.status_code == 400

    def test_threads_list(self):
        r = _req("GET", "/messages/threads", token=STATE["artist_token"])
        assert r.status_code == 200
        threads = r.json()
        assert isinstance(threads, list)
        assert any(t["other_user_id"] == STATE["artist2_id"] for t in threads)

    def test_unread_count_before_read(self):
        r = _req("GET", "/messages/unread-count", token=STATE["artist_token"])
        assert r.status_code == 200
        assert r.json()["count"] >= 1

    def test_get_thread_marks_read(self):
        r = _req("GET", f"/messages/thread/{STATE['artist2_id']}", token=STATE["artist_token"])
        assert r.status_code == 200
        d = r.json()
        assert "messages" in d
        assert len(d["messages"]) >= 2

        # unread should be 0 now for artist1
        r2 = _req("GET", "/messages/unread-count", token=STATE["artist_token"])
        assert r2.json()["count"] == 0

    def test_message_to_nonexistent_user(self):
        r = _req("POST", "/messages", token=STATE["artist_token"],
                 json={"to_user_id": "nonexistent-user-id-xyz", "text": "hi"})
        assert r.status_code == 404


# ---- NEW: Search ----
class TestSearch:
    def test_search_artworks_by_title(self):
        r = _req("GET", "/search", params={"q": "Magenta"})
        assert r.status_code == 200
        d = r.json()
        assert "artworks" in d and "artists" in d
        assert any("Magenta" in a.get("title", "") for a in d["artworks"])

    def test_search_artists_by_name(self):
        r = _req("GET", "/search", params={"q": "TEST Artist"})
        assert r.status_code == 200
        d = r.json()
        assert any(a["name"].startswith("TEST Artist") for a in d["artists"])

    def test_search_empty_returns_empty(self):
        r = _req("GET", "/search", params={"q": "   "})
        assert r.status_code == 200
        assert r.json() == {"artworks": [], "artists": []}


# ---- NEW: Feed ----
class TestFeed:
    def test_feed_returns_enriched(self):
        r = _req("GET", "/feed", token=STATE["buyer_token"])
        assert r.status_code == 200
        feed = r.json()
        assert isinstance(feed, list)
        assert len(feed) >= 1
        # find our live artwork
        item = next((a for a in feed if a["id"] == STATE["art_id_live"]), None)
        assert item is not None
        assert "artist" in item
        assert "like_count" in item
        assert "comment_count" in item
        assert "liked" in item

    def test_feed_no_auth(self):
        r = _req("GET", "/feed")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
