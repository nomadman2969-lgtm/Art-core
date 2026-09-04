"""Iteration 11 tests: messaging + attachments + read receipts + notifications + auction_ending."""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"


def _reg(role="artist"):
    tag = uuid.uuid4().hex[:8]
    email = f"test_iter11_{tag}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "Passw0rd!123",
        "name": f"IterEleven{tag}", "role": role,
    })
    assert r.status_code in (200, 201), r.text
    token = r.json()["token"]
    uid = r.json()["user"]["id"]
    return {"email": email, "token": token, "id": uid, "name": r.json()["user"]["name"],
            "h": {"Authorization": f"Bearer {token}"}}


@pytest.fixture(scope="module")
def alice():
    return _reg("artist")


@pytest.fixture(scope="module")
def bob():
    return _reg("buyer")


# ---------- Basic send + validation ----------
def test_send_self_blocked(alice):
    r = requests.post(f"{API}/messages", json={"to_user_id": alice["id"], "text": "hi"}, headers=alice["h"])
    assert r.status_code == 400


def test_send_empty_no_attachment(alice, bob):
    r = requests.post(f"{API}/messages", json={"to_user_id": bob["id"], "text": "   "}, headers=alice["h"])
    assert r.status_code == 400


def test_send_ok(alice, bob):
    r = requests.post(f"{API}/messages", json={"to_user_id": bob["id"], "text": "hello bob"}, headers=alice["h"])
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["text"] == "hello bob"
    assert m["from_id"] == alice["id"]
    assert m["to_id"] == bob["id"]
    assert m["read"] is False
    assert m["delivered_at"]
    assert "thread_key" in m


# ---------- Threads listing ----------
def test_threads_list_and_unread(alice, bob):
    r = requests.get(f"{API}/messages/threads", headers=bob["h"])
    assert r.status_code == 200
    threads = r.json()
    match = [t for t in threads if t["other_user_id"] == alice["id"]]
    assert match, f"Expected thread with alice, got: {threads}"
    t = match[0]
    assert t["unread"] >= 1
    assert t["last_from_me"] is False
    assert t["last_message"]


def test_thread_search_filter(alice, bob):
    r = requests.get(f"{API}/messages/threads", headers=bob["h"], params={"q": alice["name"][:6]})
    assert r.status_code == 200
    assert any(t["other_user_id"] == alice["id"] for t in r.json())
    r2 = requests.get(f"{API}/messages/threads", headers=bob["h"], params={"q": "zzznomatchzzz"})
    assert r2.status_code == 200
    assert r2.json() == []


# ---------- Fetch thread marks as read ----------
def test_fetch_thread_marks_read(alice, bob):
    r = requests.get(f"{API}/messages/thread/{alice['id']}", headers=bob["h"])
    assert r.status_code == 200
    data = r.json()
    assert data["other"]["id"] == alice["id"]
    for m in data["messages"]:
        if m["to_id"] == bob["id"]:
            assert m["read"] is True
            assert m["read_at"] is not None
    # Verify from alice's perspective, unread=0 now
    r2 = requests.get(f"{API}/messages/threads", headers=alice["h"])
    t = [x for x in r2.json() if x["other_user_id"] == bob["id"]][0]
    assert t["last_read"] is True


def test_unread_count(alice, bob):
    # Alice sends new msg to Bob; unread count for bob should go up
    requests.post(f"{API}/messages", json={"to_user_id": bob["id"], "text": "second msg"}, headers=alice["h"])
    r = requests.get(f"{API}/messages/unread-count", headers=bob["h"])
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_explicit_mark_read(alice, bob):
    r = requests.post(f"{API}/messages/thread/{alice['id']}/read", headers=bob["h"])
    assert r.status_code == 200
    assert r.json()["marked_read"] >= 0
    r2 = requests.get(f"{API}/messages/unread-count", headers=bob["h"])
    assert r2.json()["count"] == 0


# ---------- Search ----------
def test_search_messages(alice, bob):
    requests.post(f"{API}/messages", json={"to_user_id": bob["id"], "text": "UNIQUEXYZ needle"}, headers=alice["h"])
    r = requests.get(f"{API}/messages/search", headers=alice["h"], params={"q": "UNIQUEXYZ"})
    assert r.status_code == 200
    assert any("UNIQUEXYZ" in m["text"] for m in r.json())


# ---------- Attachments ----------
def test_attachment_unknown_kind(alice, bob):
    r = requests.post(f"{API}/messages", json={
        "to_user_id": bob["id"], "text": "x",
        "attachment": {"kind": "bogus", "ref_id": "abc"},
    }, headers=alice["h"])
    assert r.status_code == 400


def test_attachment_image_no_text_ok(alice, bob):
    r = requests.post(f"{API}/messages", json={
        "to_user_id": bob["id"], "text": "",
        "attachment": {"kind": "image", "url": "https://example.com/x.jpg", "label": "pic"},
    }, headers=alice["h"])
    assert r.status_code == 200
    a = r.json()["attachment"]
    assert a["kind"] == "image"
    assert a["url"] == "https://example.com/x.jpg"


def test_attachment_studio(alice, bob):
    r = requests.post(f"{API}/messages", json={
        "to_user_id": bob["id"], "text": "check my studio",
        "attachment": {"kind": "studio", "ref_id": alice["id"]},
    }, headers=alice["h"])
    assert r.status_code == 200
    a = r.json()["attachment"]
    assert a["kind"] == "studio"
    assert a["ref_id"] == alice["id"]
    assert a["name"] == alice["name"]


def test_attachment_artwork(alice, bob):
    # Create an artwork
    art = requests.post(f"{API}/artworks", json={
        "title": "TEST_iter11_art", "description": "d", "price": 100.0,
        "medium": "digital", "images": ["https://example.com/a.jpg"],
        "width_in": 10, "height_in": 10,
    }, headers=alice["h"])
    assert art.status_code in (200, 201), art.text
    art_id = art.json()["id"]
    # Set live status directly via publish endpoint if needed
    requests.post(f"{API}/artworks/{art_id}/publish", headers=alice["h"])
    r = requests.post(f"{API}/messages", json={
        "to_user_id": bob["id"], "text": "art",
        "attachment": {"kind": "artwork", "ref_id": art_id},
    }, headers=alice["h"])
    assert r.status_code == 200
    a = r.json()["attachment"]
    assert a["kind"] == "artwork"
    assert a["title"] == "TEST_iter11_art"
    assert a["artist_name"] == alice["name"]


def test_thread_enriches_attachments(alice, bob):
    # Send image, studio, artwork attachments freshly for isolation
    requests.post(f"{API}/messages", json={
        "to_user_id": bob["id"], "text": "img", "attachment": {"kind": "image", "url": "https://example.com/x.jpg"}
    }, headers=alice["h"])
    requests.post(f"{API}/messages", json={
        "to_user_id": bob["id"], "text": "studio", "attachment": {"kind": "studio", "ref_id": alice["id"]}
    }, headers=alice["h"])
    r = requests.get(f"{API}/messages/thread/{alice['id']}", headers=bob["h"])
    assert r.status_code == 200
    msgs = r.json()["messages"]
    kinds = [m.get("attachment", {}).get("kind") for m in msgs if m.get("attachment")]
    assert "studio" in kinds
    assert "image" in kinds


# ---------- Notification: new_message ----------
def test_new_message_notification(alice, bob):
    # Bob should have gotten a new_message notif from alice
    r = requests.get(f"{API}/notifications", headers=bob["h"])
    assert r.status_code == 200
    nm = [n for n in r.json() if n["kind"] == "new_message" and n.get("from_user_id") == alice["id"]]
    assert nm, "Expected new_message notification from alice"
    n = nm[0]
    assert n.get("other", {}).get("id") == alice["id"]


# ---------- Auction ending soon ----------
def test_auction_ending_soon_notification():
    """Create auction, DB-tweak end_at to 30min out, GET, check notification."""
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    dbname = os.environ.get("DB_NAME", "house_of_monster")
    mc = MongoClient(mongo_url)[dbname]

    artist = _reg("artist")
    buyer = _reg("buyer")
    # Create artwork
    art = requests.post(f"{API}/artworks", json={
        "title": "TEST_iter11_ending", "description": "d", "price": 50.0,
        "medium": "digital", "images": ["https://example.com/a.jpg"],
        "width_in": 10, "height_in": 10,
    }, headers=artist["h"])
    assert art.status_code in (200, 201), art.text
    art = art.json()
    # Force artwork live via DB (upload fee flow bypassed for test)
    mc.artworks.update_one({"id": art["id"]}, {"$set": {"status": "live"}})
    # Create auction with long duration first
    au = requests.post(f"{API}/auctions", json={
        "artwork_id": art["id"], "start_price": 10.0, "duration_minutes": 120,
    }, headers=artist["h"])
    assert au.status_code == 200, au.text
    aid = au.json()["id"]
    # Place a bid so we have current_bidder_id
    b = requests.post(f"{API}/auctions/{aid}/bid", json={"amount": 15.0}, headers=buyer["h"])
    assert b.status_code == 200, b.text
    # DB-hack end_at to 30min future
    new_end = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    mc.auctions.update_one({"id": aid}, {"$set": {"end_at": new_end, "ending_soon_notified": False}})
    # Trigger via GET
    g = requests.get(f"{API}/auctions/{aid}")
    assert g.status_code == 200
    # Check notification for the buyer (current_bidder)
    time.sleep(0.5)
    nots = requests.get(f"{API}/notifications", headers=buyer["h"]).json()
    ending = [n for n in nots if n["kind"] == "auction_ending" and n.get("auction_id") == aid]
    assert ending, f"Expected auction_ending notification. Got kinds: {[n['kind'] for n in nots]}"
    # Verify idempotency: hit again — no new notif
    prev_count = len(ending)
    requests.get(f"{API}/auctions/{aid}")
    nots2 = requests.get(f"{API}/notifications", headers=buyer["h"]).json()
    ending2 = [n for n in nots2 if n["kind"] == "auction_ending" and n.get("auction_id") == aid]
    assert len(ending2) == prev_count, "auction_ending should be idempotent"
