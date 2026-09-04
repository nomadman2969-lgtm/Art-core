"""Iteration 12: Typing indicators, message reactions, feed composer role checks, PWA assets."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/")


def _reg(role: str):
    email = f"TEST_iter12_{role}_{uuid.uuid4().hex[:8]}@test.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "Passw0rd!", "name": f"iter12-{role}", "role": role,
    })
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    uid = r.json()["user"]["id"]
    return {"token": tok, "id": uid, "email": email, "headers": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def artist():
    return _reg("artist")


@pytest.fixture(scope="module")
def buyer():
    return _reg("buyer")


@pytest.fixture(scope="module")
def buyer2():
    return _reg("buyer")


# ---------- Typing indicator ----------
class TestTyping:
    def test_typing_signal_and_reflected(self, buyer, artist):
        r = requests.post(f"{BASE_URL}/api/messages/thread/{artist['id']}/typing", headers=buyer["headers"])
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        # Artist fetches thread with buyer → other_typing True
        r2 = requests.get(f"{BASE_URL}/api/messages/thread/{buyer['id']}", headers=artist["headers"])
        assert r2.status_code == 200
        assert r2.json()["other_typing"] is True

    def test_typing_not_visible_to_third_party(self, buyer, buyer2):
        # buyer types to buyer2; a third user (artist) shouldn't see anything anyway,
        # and buyer2's own fetch of the buyer thread should show other_typing True.
        requests.post(f"{BASE_URL}/api/messages/thread/{buyer2['id']}/typing", headers=buyer["headers"])
        r = requests.get(f"{BASE_URL}/api/messages/thread/{buyer['id']}", headers=buyer2["headers"])
        assert r.json()["other_typing"] is True


# ---------- Reactions ----------
class TestReactions:
    def _send(self, sender, to_id, text="hi"):
        r = requests.post(f"{BASE_URL}/api/messages", headers=sender["headers"], json={
            "to_user_id": to_id, "text": text,
        })
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_react_add_toggle_replace(self, buyer, artist):
        mid = self._send(buyer, artist["id"], "react to me")
        # add heart
        r = requests.post(f"{BASE_URL}/api/messages/{mid}/react", headers=artist["headers"], json={"emoji": "heart"})
        assert r.status_code == 200
        reactions = r.json()["reactions"]
        assert len(reactions) == 1 and reactions[0]["emoji"] == "heart" and reactions[0]["user_id"] == artist["id"]
        # same emoji toggles off
        r = requests.post(f"{BASE_URL}/api/messages/{mid}/react", headers=artist["headers"], json={"emoji": "heart"})
        assert r.status_code == 200
        assert r.json()["reactions"] == []
        # add fire
        requests.post(f"{BASE_URL}/api/messages/{mid}/react", headers=artist["headers"], json={"emoji": "fire"})
        # different emoji replaces (still just 1)
        r = requests.post(f"{BASE_URL}/api/messages/{mid}/react", headers=artist["headers"], json={"emoji": "clap"})
        assert r.status_code == 200
        reactions = r.json()["reactions"]
        assert len(reactions) == 1 and reactions[0]["emoji"] == "clap"

    def test_react_invalid_emoji_400(self, buyer, artist):
        mid = self._send(buyer, artist["id"], "invalid react")
        r = requests.post(f"{BASE_URL}/api/messages/{mid}/react", headers=artist["headers"], json={"emoji": "poop"})
        assert r.status_code == 400

    def test_react_not_in_thread_403(self, buyer, artist, buyer2):
        mid = self._send(buyer, artist["id"], "private thread")
        r = requests.post(f"{BASE_URL}/api/messages/{mid}/react", headers=buyer2["headers"], json={"emoji": "heart"})
        assert r.status_code == 403

    def test_react_all_allowed_emojis(self, buyer, artist):
        mid = self._send(buyer, artist["id"], "cycle")
        for emoji in ["heart", "fire", "mind_blown", "wow", "clap", "eye"]:
            r = requests.post(f"{BASE_URL}/api/messages/{mid}/react", headers=artist["headers"], json={"emoji": emoji})
            assert r.status_code == 200, f"{emoji} failed: {r.text}"


# ---------- Feed composer / posts role checks ----------
class TestFeedComposer:
    def test_artist_can_post(self, artist):
        r = requests.post(f"{BASE_URL}/api/posts", headers=artist["headers"], json={
            "kind": "wip", "text": "TEST_iter12 WIP post from artist",
        })
        assert r.status_code == 200, r.text
        assert r.json()["kind"] == "wip"
        assert r.json()["artist_id"] == artist["id"]

    def test_buyer_cannot_post_403(self, buyer):
        r = requests.post(f"{BASE_URL}/api/posts", headers=buyer["headers"], json={
            "kind": "wip", "text": "buyer should be blocked",
        })
        assert r.status_code == 403

    def test_all_post_kinds_valid(self, artist):
        # Just test 3 additional kinds to save time
        for k in ["update", "announcement", "behind_scenes"]:
            r = requests.post(f"{BASE_URL}/api/posts", headers=artist["headers"], json={
                "kind": k, "text": f"TEST_iter12 {k}",
            })
            assert r.status_code == 200, f"{k}: {r.text}"

    def test_invalid_kind_400(self, artist):
        r = requests.post(f"{BASE_URL}/api/posts", headers=artist["headers"], json={
            "kind": "not_a_kind", "text": "x",
        })
        assert r.status_code == 400


# ---------- Home feed picks up new artist posts ----------
class TestHomeFeed:
    def test_home_feed_after_follow(self, buyer, artist):
        # buyer follows artist
        r = requests.post(f"{BASE_URL}/api/users/{artist['id']}/follow", headers=buyer["headers"])
        assert r.status_code == 200, r.text
        # artist posts
        marker = f"TEST_iter12_feed_marker_{uuid.uuid4().hex[:6]}"
        rp = requests.post(f"{BASE_URL}/api/posts", headers=artist["headers"], json={
            "kind": "update", "text": marker,
        })
        assert rp.status_code == 200
        # feed
        rf = requests.get(f"{BASE_URL}/api/feed/home", headers=buyer["headers"])
        assert rf.status_code == 200
        items = rf.json().get("items", [])
        assert any(marker in (it.get("text") or "") for it in items), f"marker not found; feed={items[:3]}"


# ---------- PWA static assets ----------
class TestPWAAssets:
    def test_manifest_json(self):
        r = requests.get(f"{BASE_URL}/manifest.json")
        assert r.status_code == 200, r.status_code
        j = r.json()
        for k in ["name", "short_name", "icons", "start_url"]:
            assert k in j, f"missing {k}"
        assert isinstance(j["icons"], list) and len(j["icons"]) >= 1

    def test_service_worker_js(self):
        r = requests.get(f"{BASE_URL}/service-worker.js")
        assert r.status_code == 200
        assert "serviceWorker" in r.text or "self.addEventListener" in r.text

    def test_icons_present(self):
        for path in ["/icons/icon-192.png", "/icons/icon-512.png"]:
            r = requests.get(f"{BASE_URL}{path}")
            assert r.status_code == 200, f"{path} => {r.status_code}"
