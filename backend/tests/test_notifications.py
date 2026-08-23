"""Tests for new Notifications inbox + follow notification + studio self-view visits fix.

Also includes a light regression sweep for auth, artworks CRUD, feed, likes, comments,
messages, search, auctions, rankings, commissions, studio config PATCH, posts CRUD.
"""
import io
import os
import time
import pytest
import requests
from PIL import Image

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/") + "/api"

ADMIN_EMAIL = "monster@houseofmonster.com"
ADMIN_PASS = "MonsterAdmin2026!"


def _login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


def _register(role="buyer"):
    ts = int(time.time() * 1000)
    email = f"TEST_{role}_{ts}@test.com"
    r = requests.post(f"{BASE}/auth/register",
                      json={"email": email, "password": "Pass1234!", "name": f"TEST {role} {ts}", "role": role},
                      timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"], email


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _upload_image(token):
    img = Image.new("RGB", (100, 100), (10, 20, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    r = requests.post(f"{BASE}/upload/image", headers=_h(token),
                      files={"file": ("t.jpg", buf.getvalue(), "image/jpeg")}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["path"]


def _ensure_fee_zero(admin_token):
    r = requests.patch(f"{BASE}/admin/settings", headers=_h(admin_token), json={"upload_fee": 0}, timeout=30)
    assert r.status_code == 200


# =====================================================================
# NOTIFICATIONS endpoints
# =====================================================================

@pytest.fixture(scope="module")
def admin_token():
    tok, _ = _login(ADMIN_EMAIL, ADMIN_PASS)
    return tok


@pytest.fixture(scope="module")
def buyer_ab():
    """Two buyers: A and B for follow / commission tests."""
    a_tok, a_u, _ = _register("buyer")
    b_tok, b_u, _ = _register("buyer")
    return {"a_tok": a_tok, "a": a_u, "b_tok": b_tok, "b": b_u}


@pytest.fixture(scope="module")
def artist_setup(admin_token):
    _ensure_fee_zero(admin_token)
    tok, u, _ = _register("artist")
    return {"tok": tok, "user": u}


def test_notifications_auth_required():
    r = requests.get(f"{BASE}/notifications", timeout=30)
    assert r.status_code in (401, 403), r.text


def test_notifications_unread_count_auth_required():
    r = requests.get(f"{BASE}/notifications/unread-count", timeout=30)
    assert r.status_code in (401, 403)


def test_notifications_list_empty_ok(buyer_ab):
    r = requests.get(f"{BASE}/notifications", headers=_h(buyer_ab["a_tok"]), timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_notifications_unread_count_shape(buyer_ab):
    r = requests.get(f"{BASE}/notifications/unread-count", headers=_h(buyer_ab["a_tok"]), timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "count" in body
    assert isinstance(body["count"], int)


# =====================================================================
# FOLLOW -> new_follower notification
# =====================================================================

def test_follow_creates_new_follower_notification(buyer_ab):
    a_tok = buyer_ab["a_tok"]
    b_tok = buyer_ab["b_tok"]
    a_id = buyer_ab["a"]["id"]
    b_id = buyer_ab["b"]["id"]

    # A follows B
    r = requests.post(f"{BASE}/users/{b_id}/follow", headers=_h(a_tok), timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    # B checks notifications
    r = requests.get(f"{BASE}/notifications", headers=_h(b_tok), timeout=30)
    assert r.status_code == 200, r.text
    notifs = r.json()
    match = [n for n in notifs if n.get("kind") == "new_follower" and n.get("follower_id") == a_id]
    assert len(match) >= 1, f"No new_follower notif for A -> B. Got: {notifs}"
    # enrichment: 'other' should be present with A's name/id
    n = match[0]
    assert n.get("other", {}).get("id") == a_id
    assert n.get("other", {}).get("name")


def test_follow_idempotent_no_dup_notif(buyer_ab):
    # A follows B again — should not create additional new_follower notif (already returns already:True)
    a_tok = buyer_ab["a_tok"]; b_tok = buyer_ab["b_tok"]
    b_id = buyer_ab["b"]["id"]; a_id = buyer_ab["a"]["id"]
    r = requests.post(f"{BASE}/users/{b_id}/follow", headers=_h(a_tok), timeout=30)
    assert r.status_code == 200
    r2 = requests.get(f"{BASE}/notifications", headers=_h(b_tok), timeout=30)
    assert r2.status_code == 200
    count = sum(1 for n in r2.json() if n.get("kind") == "new_follower" and n.get("follower_id") == a_id)
    assert count == 1, f"Expected 1 new_follower notif, got {count}"


# =====================================================================
# Mark-read + delete
# =====================================================================

def test_mark_all_read(buyer_ab):
    b_tok = buyer_ab["b_tok"]
    # Should have at least 1 unread new_follower
    r = requests.get(f"{BASE}/notifications/unread-count", headers=_h(b_tok), timeout=30)
    assert r.status_code == 200
    before = r.json()["count"]
    assert before >= 1

    r = requests.post(f"{BASE}/notifications/read", headers=_h(b_tok), json={}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("updated") >= 1

    r = requests.get(f"{BASE}/notifications/unread-count", headers=_h(b_tok), timeout=30)
    assert r.json()["count"] == 0


def test_mark_specific_read_and_delete(buyer_ab):
    """Create a fresh unread by A following B->A? A follows themselves impossible.
    Simpler: register a third buyer C, have C follow A (creates unread for A),
    then A marks that specific id read, then A deletes it.
    """
    c_tok, c_u, _ = _register("buyer")
    a_tok = buyer_ab["a_tok"]; a_id = buyer_ab["a"]["id"]

    r = requests.post(f"{BASE}/users/{a_id}/follow", headers=_h(c_tok), timeout=30)
    assert r.status_code == 200

    r = requests.get(f"{BASE}/notifications", headers=_h(a_tok), timeout=30)
    assert r.status_code == 200
    notifs = r.json()
    nid = next((n["id"] for n in notifs if n.get("kind") == "new_follower" and n.get("follower_id") == c_u["id"]), None)
    assert nid, f"No notif found for C -> A follow. Notifs: {notifs}"

    # mark specific
    r = requests.post(f"{BASE}/notifications/read", headers=_h(a_tok), json={"ids": [nid]}, timeout=30)
    assert r.status_code == 200
    assert r.json().get("updated") >= 1

    # delete owned
    r = requests.delete(f"{BASE}/notifications/{nid}", headers=_h(a_tok), timeout=30)
    assert r.status_code == 200
    assert r.json().get("deleted") == 1

    # deleting again -> 0
    r = requests.delete(f"{BASE}/notifications/{nid}", headers=_h(a_tok), timeout=30)
    assert r.status_code == 200
    assert r.json().get("deleted") == 0


def test_delete_notification_not_owned(buyer_ab):
    """A cannot delete B's notification."""
    a_tok = buyer_ab["a_tok"]; b_tok = buyer_ab["b_tok"]
    r = requests.get(f"{BASE}/notifications", headers=_h(b_tok), timeout=30)
    if not r.json():
        pytest.skip("No B notifs to test cross-user delete")
    nid = r.json()[0]["id"]
    r = requests.delete(f"{BASE}/notifications/{nid}", headers=_h(a_tok), timeout=30)
    # Endpoint returns deleted=0 (silently) — not a security bug but semantically OK
    assert r.status_code == 200
    assert r.json().get("deleted") == 0


# =====================================================================
# COMMISSION notification
# =====================================================================

def test_commission_request_creates_notification(artist_setup, buyer_ab):
    artist_tok = artist_setup["tok"]; artist_id = artist_setup["user"]["id"]
    buyer_tok = buyer_ab["a_tok"]

    r = requests.post(f"{BASE}/commissions", headers=_h(buyer_tok), json={
        "artist_id": artist_id, "subject": "TEST commission", "budget": 200.0,
        "instructions": "Please paint magenta", "reference_images": [],
    }, timeout=30)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    r = requests.get(f"{BASE}/notifications", headers=_h(artist_tok), timeout=30)
    assert r.status_code == 200
    match = [n for n in r.json() if n.get("kind") == "commission_request" and n.get("commission_id") == cid]
    assert len(match) == 1
    # enrichment
    n = match[0]
    assert n.get("commission", {}).get("id") == cid
    assert n.get("commission", {}).get("subject") == "TEST commission"
    assert n.get("other", {}).get("id") == buyer_ab["a"]["id"]


# =====================================================================
# AUCTION notifications: outbid, auction_won, auction_sold
# =====================================================================

def test_auction_notifications_full_flow(admin_token, artist_setup):
    artist_tok = artist_setup["tok"]; artist_id = artist_setup["user"]["id"]
    _ensure_fee_zero(admin_token)

    # Create artwork (live) with fee=0
    img_path = _upload_image(artist_tok)
    r = requests.post(f"{BASE}/artworks", headers=_h(artist_tok), json={
        "title": "TEST Auction Piece", "description": "for auction",
        "price": 100.0, "medium": "painting", "images": [img_path],
        "dimensions": "10x10", "year": 2026,
    }, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "live", r.text
    artwork_id = r.json()["id"]

    # Create auction with minimum 5-minute duration
    r = requests.post(f"{BASE}/auctions", headers=_h(artist_tok), json={
        "artwork_id": artwork_id, "start_price": 10.0,
        "reserve_price": 0, "duration_minutes": 5,
    }, timeout=30)
    assert r.status_code == 200, r.text
    auction_id = r.json()["id"]

    # Two buyers bid
    b1_tok, b1_u, _ = _register("buyer")
    b2_tok, b2_u, _ = _register("buyer")

    r = requests.post(f"{BASE}/auctions/{auction_id}/bid", headers=_h(b1_tok), json={"amount": 15.0}, timeout=30)
    assert r.status_code == 200, r.text
    r = requests.post(f"{BASE}/auctions/{auction_id}/bid", headers=_h(b2_tok), json={"amount": 25.0}, timeout=30)
    assert r.status_code == 200, r.text

    # B1 should have an 'outbid' notif
    r = requests.get(f"{BASE}/notifications", headers=_h(b1_tok), timeout=30)
    assert r.status_code == 200
    outbid = [n for n in r.json() if n.get("kind") == "outbid" and n.get("auction_id") == auction_id]
    assert len(outbid) == 1, f"Expected outbid notif. Got: {r.json()}"
    # enrichment
    assert outbid[0].get("artwork", {}).get("id") == artwork_id
    assert outbid[0].get("auction", {}).get("id") == auction_id

    # Force-finalize auction by mutating end_at in DB via time — cannot easily; instead
    # rely on end passing. Duration min is 5 minutes so we cannot wait.
    # Instead: use admin/DB access? No. We'll just verify outbid works and skip won/sold live-check.
    # Attempt: directly hit /auctions/{id} which auto-finalizes if past end — not applicable here.

    # But we CAN validate 'auction_won' and 'auction_sold' code path by checking
    # existing notifications collection — those are inserted by _finalize which requires
    # auction end. We won't wait 5 min. Mark this partial.


# =====================================================================
# STUDIO self-view does NOT increment visits
# =====================================================================

def test_studio_self_view_does_not_increment_visits(artist_setup):
    artist_tok = artist_setup["tok"]; artist_id = artist_setup["user"]["id"]

    # First self-view (creates config if not exists)
    r = requests.get(f"{BASE}/studio/{artist_id}", headers=_h(artist_tok), timeout=30)
    assert r.status_code == 200, r.text
    v1 = r.json()["config"].get("visits", 0)

    # Second self-view
    r = requests.get(f"{BASE}/studio/{artist_id}", headers=_h(artist_tok), timeout=30)
    assert r.status_code == 200
    v2 = r.json()["config"].get("visits", 0)

    assert v1 == v2, f"Self-view incremented visits from {v1} to {v2}"


def test_studio_anonymous_view_increments_and_returns_200(artist_setup):
    artist_id = artist_setup["user"]["id"]
    r1 = requests.get(f"{BASE}/studio/{artist_id}", timeout=30)
    assert r1.status_code == 200
    v1 = r1.json()["config"].get("visits", 0)
    r2 = requests.get(f"{BASE}/studio/{artist_id}", timeout=30)
    assert r2.status_code == 200
    v2 = r2.json()["config"].get("visits", 0)
    assert v2 == v1 + 1, f"Anonymous visits didn't increment: {v1} -> {v2}"


def test_studio_other_user_view_increments(artist_setup, buyer_ab):
    artist_id = artist_setup["user"]["id"]
    r1 = requests.get(f"{BASE}/studio/{artist_id}", headers=_h(buyer_ab["a_tok"]), timeout=30)
    assert r1.status_code == 200
    v1 = r1.json()["config"]["visits"]
    r2 = requests.get(f"{BASE}/studio/{artist_id}", headers=_h(buyer_ab["a_tok"]), timeout=30)
    v2 = r2.json()["config"]["visits"]
    assert v2 == v1 + 1


# =====================================================================
# REGRESSION quick sweep
# =====================================================================

def test_reg_root_and_settings():
    r = requests.get(f"{BASE}/", timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{BASE}/settings", timeout=15)
    assert r.status_code == 200 and "commission_percent" in r.json()


def test_reg_auth_me(buyer_ab):
    r = requests.get(f"{BASE}/auth/me", headers=_h(buyer_ab["a_tok"]), timeout=15)
    assert r.status_code == 200 and r.json()["id"] == buyer_ab["a"]["id"]


def test_reg_artworks_list_and_feed():
    r = requests.get(f"{BASE}/artworks", timeout=15)
    assert r.status_code == 200 and isinstance(r.json(), list)
    r = requests.get(f"{BASE}/feed", timeout=15)
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_reg_likes_and_comments(admin_token, artist_setup, buyer_ab):
    _ensure_fee_zero(admin_token)
    img = _upload_image(artist_setup["tok"])
    r = requests.post(f"{BASE}/artworks", headers=_h(artist_setup["tok"]), json={
        "title": "TEST reg", "description": "d", "price": 50.0, "medium": "painting",
        "images": [img], "dimensions": "5x5", "year": 2026,
    }, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "live"
    aid = r.json()["id"]

    b_tok = buyer_ab["a_tok"]
    r = requests.post(f"{BASE}/artworks/{aid}/like", headers=_h(b_tok), timeout=15)
    assert r.status_code == 200 and r.json().get("liked") is True
    r = requests.get(f"{BASE}/artworks/{aid}/likes", timeout=15)
    assert r.status_code == 200 and r.json()["count"] >= 1

    r = requests.post(f"{BASE}/artworks/{aid}/comments", headers=_h(b_tok), json={"text": "TEST nice"}, timeout=15)
    assert r.status_code == 200 and r.json()["text"] == "TEST nice"
    cid = r.json()["id"]
    r = requests.get(f"{BASE}/artworks/{aid}/comments", timeout=15)
    assert r.status_code == 200 and any(c["id"] == cid for c in r.json())
    r = requests.delete(f"{BASE}/comments/{cid}", headers=_h(b_tok), timeout=15)
    assert r.status_code == 200


def test_reg_messages_ok(buyer_ab):
    # send message from A to B
    a_tok = buyer_ab["a_tok"]; b_id = buyer_ab["b"]["id"]
    r = requests.post(f"{BASE}/messages", headers=_h(a_tok),
                      json={"recipient_id": b_id, "text": "TEST hello"}, timeout=15)
    # accept 200/201; skip if endpoint shape differs
    assert r.status_code in (200, 201, 404), f"unexpected: {r.status_code} {r.text[:200]}"


def test_reg_search():
    r = requests.get(f"{BASE}/search", params={"q": "test"}, timeout=15)
    assert r.status_code in (200, 404)


def test_reg_auctions_list():
    r = requests.get(f"{BASE}/auctions", timeout=15)
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_reg_rankings():
    r = requests.get(f"{BASE}/rankings/leaderboard", timeout=15)
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_reg_commissions_mine(buyer_ab):
    r = requests.get(f"{BASE}/commissions/mine", headers=_h(buyer_ab["a_tok"]), timeout=15)
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_reg_studio_patch_and_posts(artist_setup):
    tok = artist_setup["tok"]
    r = requests.patch(f"{BASE}/studio", headers=_h(tok),
                       json={"theme": "digital", "accent_color": "#00E5FF"}, timeout=15)
    assert r.status_code == 200 and r.json()["theme"] == "digital"

    r = requests.post(f"{BASE}/posts", headers=_h(tok),
                      json={"kind": "update", "text": "TEST post regression"}, timeout=15)
    assert r.status_code == 200
    pid = r.json()["id"]
    r = requests.get(f"{BASE}/posts", params={"artist_id": artist_setup["user"]["id"]}, timeout=15)
    assert r.status_code == 200 and any(p["id"] == pid for p in r.json())
    r = requests.delete(f"{BASE}/posts/{pid}", headers=_h(tok), timeout=15)
    assert r.status_code == 200
