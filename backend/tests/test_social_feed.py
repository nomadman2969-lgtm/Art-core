"""Iteration 9 backend tests: home feed, saves+collections, replies, mentions, shares, followers list."""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "house_of_monster")


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def artist(db):
    email = f"TEST_artist_{_uid()}@t.com"
    name = f"TESTArtist{_uid()}"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "pass123", "name": name, "role": "artist"
    })
    assert r.status_code in (200, 201), r.text
    tok = r.json()["token"]
    u = r.json()["user"]
    return {"token": tok, "id": u["id"], "name": name, "email": email,
            "headers": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def buyer(db):
    email = f"TEST_buyer_{_uid()}@t.com"
    name = f"TESTBuyer{_uid()}"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "pass123", "name": name, "role": "buyer"
    })
    assert r.status_code in (200, 201), r.text
    tok = r.json()["token"]
    u = r.json()["user"]
    return {"token": tok, "id": u["id"], "name": name, "email": email,
            "headers": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def live_artwork(db, artist):
    # Create an artwork then force status=live in DB (bypass Stripe upload_fee)
    payload = {
        "title": f"TEST Piece {_uid()}",
        "description": "A test artwork",
        "price": 150.0, "medium": "digital", "images": ["/uploads/x.jpg"],
        "year": 2026, "dimensions": "10x10", "width_in": 10, "height_in": 10,
    }
    r = requests.post(f"{API}/artworks", json=payload, headers=artist["headers"])
    assert r.status_code in (200, 201), r.text
    aid = r.json()["id"]
    db.artworks.update_one({"id": aid}, {"$set": {"status": "live"}})
    return aid


@pytest.fixture(scope="module")
def studio_post(artist):
    r = requests.post(f"{API}/posts", json={
        "kind": "update", "text": f"Hello world from studio! @{_uid()}"
    }, headers=artist["headers"])
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


# ---------- Follow + Home feed ----------
class TestHomeFeed:
    def test_empty_feed_no_follows(self, buyer):
        r = requests.get(f"{API}/feed/home", headers=buyer["headers"])
        assert r.status_code == 200
        data = r.json()
        # buyer at this point might or might not follow — but for fresh account
        assert "following_count" in data and "items" in data

    def test_follow_then_feed_populated(self, buyer, artist, live_artwork, studio_post):
        # buyer follows artist
        r = requests.post(f"{API}/users/{artist['id']}/follow", headers=buyer["headers"])
        assert r.status_code == 200
        # fetch home feed
        r = requests.get(f"{API}/feed/home", headers=buyer["headers"])
        assert r.status_code == 200
        data = r.json()
        assert data["following_count"] >= 1
        assert len(data["items"]) >= 2
        kinds = {i["timeline_kind"] for i in data["items"]}
        assert "post" in kinds
        assert "artwork" in kinds
        # check enrichment
        for it in data["items"]:
            assert "artist" in it and "name" in it["artist"]
            assert "timeline_at" in it
            if it["timeline_kind"] == "artwork":
                assert "like_count" in it and "comment_count" in it and "liked" in it


# ---------- Followers / Following lists ----------
class TestFollowersLists:
    def test_followers_list(self, artist, buyer):
        r = requests.get(f"{API}/users/{artist['id']}/followers", headers=buyer["headers"])
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        assert any(u["id"] == buyer["id"] for u in arr)
        for u in arr:
            assert "is_following" in u

    def test_following_list(self, artist, buyer):
        r = requests.get(f"{API}/users/{buyer['id']}/following", headers=buyer["headers"])
        assert r.status_code == 200
        arr = r.json()
        assert any(u["id"] == artist["id"] for u in arr)


# ---------- Comment replies + mentions ----------
class TestCommentsReplies:
    def test_top_level_comment_creates_new_comment_notif(self, artist, buyer, live_artwork, db):
        r = requests.post(f"{API}/artworks/{live_artwork}/comments",
                          json={"text": "Great piece!"}, headers=buyer["headers"])
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        # artist should get 'new_comment' notif
        n = db.notifications.find_one({"user_id": artist["id"], "kind": "new_comment", "comment_id": cid})
        assert n is not None
        return cid

    def test_reply_creates_nested_and_reply_notif(self, artist, buyer, live_artwork, db):
        # Top-level from buyer
        r = requests.post(f"{API}/artworks/{live_artwork}/comments",
                          json={"text": "Parent"}, headers=buyer["headers"])
        parent_id = r.json()["id"]
        # Reply from artist to buyer
        r2 = requests.post(f"{API}/artworks/{live_artwork}/comments",
                           json={"text": "Thanks!", "parent_id": parent_id},
                           headers=artist["headers"])
        assert r2.status_code == 200, r2.text
        rc = r2.json()
        assert rc["parent_id"] == parent_id
        # buyer receives comment_reply notif
        n = db.notifications.find_one({"user_id": buyer["id"], "kind": "comment_reply", "comment_id": rc["id"]})
        assert n is not None
        # threaded listing returns replies nested
        lr = requests.get(f"{API}/artworks/{live_artwork}/comments")
        assert lr.status_code == 200
        comments = lr.json()
        # find the parent
        parent = next((c for c in comments if c["id"] == parent_id), None)
        assert parent is not None
        assert "replies" in parent
        assert any(rep["id"] == rc["id"] for rep in parent["replies"])

    def test_mention_in_comment_notifies_target(self, artist, buyer, live_artwork, db):
        # buyer mentions artist by name
        text = f"cc @{artist['name']} awesome"
        r = requests.post(f"{API}/artworks/{live_artwork}/comments",
                          json={"text": text}, headers=buyer["headers"])
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        mentions = r.json().get("mentions", [])
        assert any(m["user_id"] == artist["id"] for m in mentions), f"mentions={mentions}"
        n = db.notifications.find_one({"user_id": artist["id"], "kind": "mentioned_in_comment", "comment_id": cid})
        assert n is not None


# ---------- Shares ----------
class TestShares:
    def test_share_increments_count_and_notifies(self, artist, buyer, live_artwork, db):
        r = requests.post(f"{API}/artworks/{live_artwork}/share",
                          json={"target": "copy_link"}, headers=buyer["headers"])
        assert r.status_code == 200
        data = r.json()
        assert data["shared"] is True
        assert data["count"] >= 1
        # artist should receive notification
        n = db.notifications.find_one({"user_id": artist["id"], "kind": "artwork_shared",
                                       "artwork_id": live_artwork, "from_user_id": buyer["id"]})
        assert n is not None
        # throttle: second share same day should not create another notif
        r2 = requests.post(f"{API}/artworks/{live_artwork}/share",
                           json={"target": "copy_link"}, headers=buyer["headers"])
        assert r2.status_code == 200
        cnt = db.notifications.count_documents({"user_id": artist["id"], "kind": "artwork_shared",
                                                "artwork_id": live_artwork, "from_user_id": buyer["id"]})
        assert cnt == 1

    def test_get_shares_count(self, live_artwork):
        r = requests.get(f"{API}/artworks/{live_artwork}/shares")
        assert r.status_code == 200
        assert r.json()["count"] >= 1


# ---------- Save + Collections ----------
class TestSaveCollections:
    def test_save_and_is_saved(self, buyer, live_artwork):
        r = requests.post(f"{API}/artworks/{live_artwork}/save", json={}, headers=buyer["headers"])
        assert r.status_code == 200
        assert r.json()["saved"] is True
        r2 = requests.get(f"{API}/artworks/{live_artwork}/saved", headers=buyer["headers"])
        assert r2.status_code == 200
        assert r2.json()["saved"] is True

    def test_collections_mine_has_all_saved(self, buyer):
        r = requests.get(f"{API}/collections/mine", headers=buyer["headers"])
        assert r.status_code == 200
        cols = r.json()
        assert len(cols) >= 1
        assert cols[0]["id"] == "all"
        assert cols[0]["is_all"] is True
        assert cols[0]["item_count"] >= 1

    def test_create_collection_and_save_to_it(self, buyer, live_artwork):
        cname = f"TEST col {_uid()}"
        r = requests.post(f"{API}/collections",
                          json={"name": cname, "description": "d", "is_private": True},
                          headers=buyer["headers"])
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        # save to specific collection
        r2 = requests.post(f"{API}/artworks/{live_artwork}/save",
                           json={"collection_id": cid}, headers=buyer["headers"])
        assert r2.status_code == 200
        r3 = requests.get(f"{API}/collections/{cid}", headers=buyer["headers"])
        assert r3.status_code == 200
        data = r3.json()
        assert data["collection"]["name"] == cname
        assert any(i["id"] == live_artwork for i in data["items"])
        assert data["items"][0].get("artist", {}).get("name")

        # delete collection soft-deletes but keeps saves as uncategorized
        r4 = requests.delete(f"{API}/collections/{cid}", headers=buyer["headers"])
        assert r4.status_code == 200
        # detail should now 404
        r5 = requests.get(f"{API}/collections/{cid}", headers=buyer["headers"])
        assert r5.status_code == 404

    def test_unsave_removes(self, buyer, live_artwork):
        # Unsave the "all"/default save
        r = requests.delete(f"{API}/artworks/{live_artwork}/save", headers=buyer["headers"])
        assert r.status_code == 200


# ---------- Notifications enrichment ----------
class TestNotificationsEnrichment:
    def test_notifications_enriched(self, artist):
        r = requests.get(f"{API}/notifications", headers=artist["headers"])
        assert r.status_code == 200
        arr = r.json()
        # At this point artist should have a few new-kind notifs
        social_kinds = {"new_comment", "comment_reply", "artwork_shared",
                        "mentioned_in_comment", "post_liked", "post_comment",
                        "mentioned_in_post_comment", "mentioned_in_post"}
        social_notifs = [n for n in arr if n.get("kind") in social_kinds]
        assert len(social_notifs) >= 1
        for n in social_notifs:
            if n.get("from_user_id"):
                assert "other" in n and "id" in n["other"] and "name" in n["other"]
            if n.get("artwork_id"):
                assert "artwork" in n and n["artwork"].get("title") is not None


# ---------- Post likes/comments ----------
class TestPostEngagement:
    def test_like_post_and_notify(self, artist, buyer, studio_post, db):
        r = requests.post(f"{API}/posts/{studio_post}/like", headers=buyer["headers"])
        assert r.status_code == 200
        assert r.json()["liked"] is True
        n = db.notifications.find_one({"user_id": artist["id"], "kind": "post_liked", "post_id": studio_post})
        assert n is not None

    def test_comment_on_post_and_notify(self, artist, buyer, studio_post, db):
        r = requests.post(f"{API}/posts/{studio_post}/comments",
                          json={"text": "nice post!"}, headers=buyer["headers"])
        assert r.status_code == 200
        n = db.notifications.find_one({"user_id": artist["id"], "kind": "post_comment", "post_id": studio_post})
        assert n is not None


# ---------- Regression: existing endpoints still healthy ----------
class TestRegression:
    def test_marketplace_feed(self):
        r = requests.get(f"{API}/feed")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_login_admin(self):
        r = requests.post(f"{API}/auth/login", json={
            "email": "monster@houseofmonster.com", "password": "MonsterAdmin2026!"
        })
        assert r.status_code == 200
        assert "token" in r.json()

    def test_studio_templates(self):
        r = requests.get(f"{API}/studio/templates")
        assert r.status_code == 200
        assert len(r.json()) >= 4
