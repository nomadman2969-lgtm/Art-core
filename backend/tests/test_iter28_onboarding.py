"""Iteration 28 — onboarding without a tour.

Covers:
- GET /api/studio/setup-checklist (artist JWT) shape + defaults
- POST /api/studio/setup-checklist/{shared,dismiss,restore} flows
- Unknown action -> 400
- PATCH /api/auth/me flips profile.done (avatar + bio >=20 chars)
- Upload image + create artwork flips artwork.done
- Route ordering: /setup-checklist must NOT be shadowed by /{artist_id}
- GET /api/settings includes stripe_mode
"""
import io
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _register_artist():
    email = f"iter28_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email,
        "password": "TestArtist28!",
        "name": "Iter28 Tester",
        "role": "artist",
    }, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"no token in register response: {data}"
    return email, token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Settings ----------

def test_settings_has_stripe_mode():
    r = requests.get(f"{API}/settings", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "stripe_mode" in body, body
    assert body["stripe_mode"] in ("test", "live")


# ---------- Setup checklist ----------

class TestSetupChecklist:
    def test_fresh_artist_all_zero(self):
        _, token = _register_artist()
        r = requests.get(f"{API}/studio/setup-checklist", headers=_auth(token), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 5
        assert body["done"] == 0
        assert body["complete"] is False
        assert body["dismissed"] is False
        keys = [s["key"] for s in body["steps"]]
        assert keys == ["profile", "artwork", "payouts", "publish", "share"], keys
        for s in body["steps"]:
            assert s["done"] is False, s

    def test_share_action_increments_done(self):
        _, token = _register_artist()
        r = requests.post(f"{API}/studio/setup-checklist/shared", headers=_auth(token), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        r = requests.get(f"{API}/studio/setup-checklist", headers=_auth(token), timeout=15)
        assert r.status_code == 200
        body = r.json()
        share = next(s for s in body["steps"] if s["key"] == "share")
        assert share["done"] is True
        assert body["done"] == 1

    def test_dismiss_then_restore(self):
        _, token = _register_artist()
        r = requests.post(f"{API}/studio/setup-checklist/dismiss", headers=_auth(token), timeout=15)
        assert r.status_code == 200
        b = requests.get(f"{API}/studio/setup-checklist", headers=_auth(token), timeout=15).json()
        assert b["dismissed"] is True

        r = requests.post(f"{API}/studio/setup-checklist/restore", headers=_auth(token), timeout=15)
        assert r.status_code == 200
        b = requests.get(f"{API}/studio/setup-checklist", headers=_auth(token), timeout=15).json()
        assert b["dismissed"] is False

    def test_unknown_action_400(self):
        _, token = _register_artist()
        r = requests.post(f"{API}/studio/setup-checklist/bogus", headers=_auth(token), timeout=15)
        assert r.status_code == 400, r.text

    def test_not_shadowed_by_artist_id_route(self):
        """Regression: /setup-checklist must not fall through to /{artist_id} → 404 'Artist not found'."""
        _, token = _register_artist()
        r = requests.get(f"{API}/studio/setup-checklist", headers=_auth(token), timeout=15)
        assert r.status_code == 200, r.text
        assert "Artist not found" not in r.text

    def test_profile_flips_after_patch_me(self):
        _, token = _register_artist()
        payload = {
            "avatar": "https://example.com/pic.jpg",
            "bio": "I am a working artist based in NYC making mixed-media pieces.",
        }
        assert len(payload["bio"]) >= 20
        r = requests.patch(f"{API}/auth/me", headers=_auth(token), json=payload, timeout=15)
        assert r.status_code == 200, r.text

        b = requests.get(f"{API}/studio/setup-checklist", headers=_auth(token), timeout=15).json()
        profile = next(s for s in b["steps"] if s["key"] == "profile")
        assert profile["done"] is True, b

    def test_profile_not_done_with_short_bio(self):
        _, token = _register_artist()
        r = requests.patch(f"{API}/auth/me", headers=_auth(token),
                           json={"avatar": "https://ex.com/a.jpg", "bio": "short"}, timeout=15)
        assert r.status_code == 200
        b = requests.get(f"{API}/studio/setup-checklist", headers=_auth(token), timeout=15).json()
        profile = next(s for s in b["steps"] if s["key"] == "profile")
        assert profile["done"] is False

    def test_artwork_flips_after_upload_and_create(self):
        _, token = _register_artist()

        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (10, 10), (255, 0, 0)).save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        r = requests.post(f"{API}/upload/image", headers=_auth(token), files=files, timeout=30)
        assert r.status_code == 200, r.text
        storage_path = r.json()["path"]

        art_payload = {
            "title": "Test Piece",
            "description": "A test artwork",
            "medium": "oil",
            "style": "abstract",
            "color": "red",
            "width_in": 12.0,
            "height_in": 12.0,
            "price": 100.0,
            "images": [storage_path],
        }
        r = requests.post(f"{API}/artworks", headers=_auth(token), json=art_payload, timeout=30)
        assert r.status_code in (200, 201), r.text

        b = requests.get(f"{API}/studio/setup-checklist", headers=_auth(token), timeout=15).json()
        aw = next(s for s in b["steps"] if s["key"] == "artwork")
        assert aw["done"] is True, b
