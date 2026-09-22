"""Iteration 27 — Launch page / private files / attendees / poster / consent / demo-login gate."""
import os
import io
import pytest
import requests
from datetime import datetime, timedelta, timezone

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass
    return None

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL not set"
ADMIN_EMAIL = "monster@houseofmonster.com"
ADMIN_PW = os.environ.get("ADMIN_PASSWORD") or "atg-6+XxIRZe1zLUDCcwB!_a"
ARTIST_EMAIL = "demo.artist@artcorestudio.net"
ARTIST_PW = "DemoArtist2026!"
COLLECTOR_EMAIL = "demo.collector@artcorestudio.net"
COLLECTOR_PW = "DemoCollector2026!"
STRANGER_EMAIL = "stranger.pf@example.com"
STRANGER_PW = "Stranger123!"


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed {email}: {r.status_code} {r.text[:200]}")
    return r.json()["token"], r.json().get("user", {})


@pytest.fixture(scope="session")
def admin_tok():
    tok, _ = _login(ADMIN_EMAIL, ADMIN_PW)
    return tok


@pytest.fixture(scope="session")
def artist_ctx():
    tok, user = _login(ARTIST_EMAIL, ARTIST_PW)
    return {"tok": tok, "id": user["id"], "name": user["name"]}


@pytest.fixture(scope="session")
def collector_ctx():
    tok, user = _login(COLLECTOR_EMAIL, COLLECTOR_PW)
    return {"tok": tok, "id": user["id"], "name": user["name"]}


@pytest.fixture(scope="session")
def stranger_tok():
    # ensure exists
    r = requests.post(f"{BASE}/api/auth/register",
                      json={"email": STRANGER_EMAIL, "password": STRANGER_PW, "name": "Stranger", "role": "buyer"},
                      timeout=15)
    tok, _ = _login(STRANGER_EMAIL, STRANGER_PW)
    return tok


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ============ Public artist endpoints — no email leaked ============
class TestPublicArtistsHideEmail:
    def test_list_artists_no_email(self):
        r = requests.get(f"{BASE}/api/artists", timeout=20)
        assert r.status_code == 200
        arts = r.json()
        assert isinstance(arts, list) and len(arts) > 0
        for a in arts:
            assert "email" not in a, f"artist leaks email: {a}"

    def test_artist_detail_no_email(self, artist_ctx):
        r = requests.get(f"{BASE}/api/artists/{artist_ctx['id']}", timeout=20)
        assert r.status_code == 200
        assert "email" not in r.json()

    def test_search_demo_no_email(self):
        r = requests.get(f"{BASE}/api/search", params={"q": "demo"}, timeout=20)
        assert r.status_code == 200
        # search returns different sections; walk everything and assert no email keys on user-shaped dicts
        def walk(x):
            if isinstance(x, dict):
                if "role" in x and "name" in x:
                    assert "email" not in x, f"search leaks email: {x}"
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x: walk(v)
        walk(r.json())

    def test_auth_me_has_email(self, collector_ctx):
        r = requests.get(f"{BASE}/api/auth/me", headers=_h(collector_ctx["tok"]), timeout=20)
        assert r.status_code == 200
        assert r.json().get("email") == COLLECTOR_EMAIL


# ============ Attendees endpoint ============
class TestAttendeesAuth:
    @pytest.fixture(scope="class")
    def event_id(self, artist_ctx):
        # create a fresh free event with the demo artist as host
        start = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        payload = {
            "title": "TEST_iter27 Launch Event",
            "description": "test event for iter27",
            "category": "gallery_opening",
            "location": {"lat": 40.7, "lng": -74.0, "city": "NYC"},
            "start_at": start,
            "is_free": True,
        }
        r = requests.post(f"{BASE}/api/events", json=payload, headers=_h(artist_ctx["tok"]), timeout=20)
        assert r.status_code == 200, r.text
        eid = r.json()["id"]
        yield eid
        # cleanup
        requests.delete(f"{BASE}/api/events/{eid}", headers=_h(artist_ctx["tok"]), timeout=15)

    def test_attendees_anon_401(self, event_id):
        r = requests.get(f"{BASE}/api/events/{event_id}/attendees", timeout=20)
        assert r.status_code == 401

    def test_attendees_non_host_minimal(self, event_id, collector_ctx, stranger_tok):
        # collector rsvps
        r = requests.post(f"{BASE}/api/events/{event_id}/rsvp", headers=_h(collector_ctx["tok"]), timeout=20)
        assert r.status_code == 200
        # stranger fetches attendees
        r = requests.get(f"{BASE}/api/events/{event_id}/attendees", headers=_h(stranger_tok), timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) >= 1
        for row in rows:
            assert set(row.keys()) <= {"id", "user_id", "user_name", "created_at", "gift"}, f"leak: {row}"
            for banned in ("user_email", "paid", "amount", "checked_in"):
                assert banned not in row, f"leaked {banned}"

    def test_attendees_host_full(self, event_id, artist_ctx):
        r = requests.get(f"{BASE}/api/events/{event_id}/attendees", headers=_h(artist_ctx["tok"]), timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) >= 1
        # host must see the extended keys (even if values are None/False)
        for row in rows:
            for k in ("user_email", "paid", "amount", "checked_in"):
                assert k in row, f"host missing {k}: {row}"

    def test_attendees_admin_full(self, event_id, admin_tok):
        r = requests.get(f"{BASE}/api/events/{event_id}/attendees", headers=_h(admin_tok), timeout=20)
        assert r.status_code == 200
        for row in r.json():
            assert "user_email" in row and "paid" in row


# ============ Poster endpoint ============
class TestPoster:
    def test_poster_png(self, artist_ctx):
        # find an existing non-cancelled event by the demo artist
        r = requests.get(f"{BASE}/api/events", params={"host_id": artist_ctx["id"], "upcoming_only": False, "limit": 20}, timeout=20)
        assert r.status_code == 200
        evs = [e for e in r.json() if not e.get("cancelled")]
        if not evs:
            pytest.skip("no event to render poster for")
        eid = evs[0]["id"]
        r = requests.get(f"{BASE}/api/events/{eid}/poster.png", timeout=45)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/png")
        # PNG magic + IHDR size check
        b = r.content
        assert b[:8] == b"\x89PNG\r\n\x1a\n"
        # width big-endian at offset 16, height at 20
        w = int.from_bytes(b[16:20], "big")
        h = int.from_bytes(b[20:24], "big")
        assert (w, h) == (1080, 1620), f"got {w}x{h}"

    def test_poster_unknown_404(self):
        r = requests.get(f"{BASE}/api/events/does-not-exist/poster.png", timeout=15)
        assert r.status_code == 404


# ============ Private files: signed URL from DM ============
class TestPrivateFilesDM:
    def test_dm_image_signed_url_flow(self, collector_ctx, artist_ctx, stranger_tok):
        # 1. Upload as collector — public endpoint returns path
        img = _tiny_jpeg()
        files = {"file": ("test.jpg", img, "image/jpeg")}
        r = requests.post(f"{BASE}/api/upload/image", files=files, headers=_h(collector_ctx["tok"]), timeout=90)
        assert r.status_code == 200, r.text
        upload_data = r.json()
        raw_url = upload_data["url"]
        print(f"UPLOAD_DATA={upload_data}")
        # raw path is public BEFORE mark_private (still cacheable)
        rp = requests.get(f"{BASE}{raw_url}", timeout=15)
        assert rp.status_code == 200

        # 2. Send DM to artist with image attachment — this marks it private
        body = {"to_user_id": artist_ctx["id"], "text": "test iter27 image",
                "attachment": {"kind": "image", "url": raw_url}}
        r = requests.post(f"{BASE}/api/messages", json=body, headers=_h(collector_ctx["tok"]), timeout=20)
        assert r.status_code == 200, r.text

        # 3. Anon GET → 401
        r = requests.get(f"{BASE}{raw_url}", timeout=15)
        assert r.status_code == 401

        # 4. Stranger → 403
        r = requests.get(f"{BASE}{raw_url}", headers=_h(stranger_tok), timeout=15)
        assert r.status_code == 403

        # 5. Artist (thread member) → 200 + private cache
        r = requests.get(f"{BASE}{raw_url}", headers=_h(artist_ctx["tok"]), timeout=15)
        assert r.status_code == 200
        assert "no-store" in r.headers.get("cache-control", "").lower()

        # 6. Thread list for collector should include signed_url
        r = requests.get(f"{BASE}/api/messages/thread/{artist_ctx['id']}", headers=_h(collector_ctx["tok"]), timeout=20)
        assert r.status_code == 200
        data = r.json()
        msgs = data.get("messages", [])
        # find our specific just-sent msg — signed_url should contain the raw path stem
        stem = raw_url.rsplit("/", 1)[-1].split(".")[0]  # uuid stem
        found = None
        for m in reversed(msgs):
            a = m.get("attachment") or {}
            if isinstance(a, dict) and a.get("kind") == "image" and stem in (a.get("signed_url") or ""):
                found = a; break
        assert found, f"no signed_url image attachment with stem {stem} found. last msg={msgs[-1] if msgs else None}"

        signed = found["signed_url"]
        # 7. Anon with signed url → 200
        r = requests.get(f"{BASE}{signed}", timeout=15)
        assert r.status_code == 200, f"signed={signed} status={r.status_code} body={r.text[:200]}"

        # 8. Tampered sig → 401
        bad = signed.replace("sig=", "sig=deadbeef")
        # ensure actually different
        if bad == signed:
            bad = signed[:-4] + "0000"
        else:
            # replace the value after sig=
            import re
            bad = re.sub(r"sig=[a-f0-9]+", "sig=" + ("0" * 40), signed)
        r = requests.get(f"{BASE}{bad}", timeout=15)
        assert r.status_code == 401


def _tiny_jpeg() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 100, 50)).save(buf, format="JPEG", quality=70)
    return buf.getvalue()


# ============ Demo-login gate ============
class TestDemoLoginGate:
    def test_toggle_demo_gate(self, admin_tok):
        # ON (default) — works
        r = requests.post(f"{BASE}/api/auth/demo-login", json={"role": "artist"}, timeout=15)
        assert r.status_code == 200, r.text

        # Turn OFF
        r = requests.patch(f"{BASE}/api/admin/settings", json={"demo_login_enabled": False},
                           headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        r = requests.post(f"{BASE}/api/auth/demo-login", json={"role": "collector"}, timeout=15)
        assert r.status_code == 403

        # Restore ON
        r = requests.patch(f"{BASE}/api/admin/settings", json={"demo_login_enabled": True},
                           headers=_h(admin_tok), timeout=15)
        assert r.status_code == 200
        r = requests.post(f"{BASE}/api/auth/demo-login", json={"role": "collector"}, timeout=15)
        assert r.status_code == 200
