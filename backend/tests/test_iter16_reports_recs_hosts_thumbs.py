"""Iteration 16: reports moderation, event recommendations, host pages, thumbnails."""
import os
import io
import pytest
import requests
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

COLLECTOR = ("demo.collector@artcorestudio.net", "DemoCollector2026!")
ARTIST = ("demo.artist@artcorestudio.net", "DemoArtist2026!")
ADMIN = ("monster@houseofmonster.com", "MonsterAdmin2026!")


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, headers=UA, timeout=30)
    assert r.status_code == 200, f"login {email} {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _h(tok):
    return {**UA, "Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def tokens():
    return {"c": _login(*COLLECTOR), "a": _login(*ARTIST), "admin": _login(*ADMIN)}


@pytest.fixture(scope="module")
def ids(tokens):
    me_c = requests.get(f"{BASE}/api/auth/me", headers=_h(tokens["c"])).json()
    me_a = requests.get(f"{BASE}/api/auth/me", headers=_h(tokens["a"])).json()
    return {"collector_id": me_c["id"], "artist_id": me_a["id"]}


# ------------- Reports ---------------
class TestReports:
    def test_create_report_artwork_ok(self, tokens, ids):
        # find an artwork not owned by collector; use one from any live artist
        arts = requests.get(f"{BASE}/api/artworks?limit=60", headers=UA).json()
        target = next((a for a in arts if a["artist_id"] != ids["collector_id"]), None)
        assert target, "no artworks"
        # cleanup previously open report
        r = requests.post(f"{BASE}/api/reports",
                          json={"target_type": "artwork", "target_id": target["id"], "reason": "spam", "details": "iter16 test"},
                          headers=_h(tokens["c"]))
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            assert r.json()["ok"] is True and r.json().get("id")
        pytest.report_target = target
        pytest.report_id_created = r.json().get("id") if r.status_code == 200 else None

    def test_duplicate_report_400(self, tokens):
        target = pytest.report_target
        r = requests.post(f"{BASE}/api/reports",
                          json={"target_type": "artwork", "target_id": target["id"], "reason": "spam"},
                          headers=_h(tokens["c"]))
        assert r.status_code == 400

    def test_invalid_target_type_422(self, tokens):
        r = requests.post(f"{BASE}/api/reports",
                          json={"target_type": "banana", "target_id": "x", "reason": "spam"},
                          headers=_h(tokens["c"]))
        assert r.status_code == 422

    def test_invalid_reason_422(self, tokens):
        target = pytest.report_target
        r = requests.post(f"{BASE}/api/reports",
                          json={"target_type": "artwork", "target_id": target["id"], "reason": "weird"},
                          headers=_h(tokens["c"]))
        assert r.status_code == 422

    def test_unknown_target_404(self, tokens):
        r = requests.post(f"{BASE}/api/reports",
                          json={"target_type": "artwork", "target_id": "does-not-exist", "reason": "spam"},
                          headers=_h(tokens["c"]))
        assert r.status_code == 404

    def test_report_own_content_400(self, tokens, ids):
        arts = requests.get(f"{BASE}/api/artworks?artist_id={ids['artist_id']}&limit=1", headers=UA).json()
        assert arts
        r = requests.post(f"{BASE}/api/reports",
                          json={"target_type": "artwork", "target_id": arts[0]["id"], "reason": "spam"},
                          headers=_h(tokens["a"]))
        assert r.status_code == 400

    def test_unauth_401(self):
        r = requests.post(f"{BASE}/api/reports",
                          json={"target_type": "artwork", "target_id": "x", "reason": "spam"},
                          headers=UA)
        assert r.status_code in (401, 403)

    def test_admin_list_and_stats(self, tokens):
        r = requests.get(f"{BASE}/api/admin/reports?status=open", headers=_h(tokens["admin"]))
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        it = items[0]
        assert "reporter" in it
        # target/owner may be missing if content was already removed; just require reporter
        s = requests.get(f"{BASE}/api/admin/reports/stats", headers=_h(tokens["admin"]))
        assert s.status_code == 200
        assert "open" in s.json() and "total" in s.json()

    def test_non_admin_list_403(self, tokens):
        r = requests.get(f"{BASE}/api/admin/reports", headers=_h(tokens["c"]))
        assert r.status_code == 403

    def test_resolve_dismiss_and_double_400(self, tokens):
        # find our open report on the artwork target
        items = requests.get(f"{BASE}/api/admin/reports?status=open", headers=_h(tokens["admin"])).json()
        target = pytest.report_target
        mine = next((it for it in items if it["target_type"] == "artwork" and it["target_id"] == target["id"]), None)
        assert mine, "our open report not listed"
        r = requests.post(f"{BASE}/api/admin/reports/{mine['id']}/resolve",
                          json={"action": "dismiss", "note": "iter16"}, headers=_h(tokens["admin"]))
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"
        r2 = requests.post(f"{BASE}/api/admin/reports/{mine['id']}/resolve",
                           json={"action": "dismiss"}, headers=_h(tokens["admin"]))
        assert r2.status_code == 400

    def test_invalid_action_400(self, tokens):
        # create new open report against artist's artwork by collector
        arts = requests.get(f"{BASE}/api/artworks?artist_id={_uid(tokens['a'])}&limit=2", headers=UA).json()
        # use one; skip already-hidden
        for a in arts:
            r = requests.post(f"{BASE}/api/reports",
                              json={"target_type": "artwork", "target_id": a["id"], "reason": "other"},
                              headers=_h(tokens["c"]))
            if r.status_code == 200:
                rid = r.json()["id"]
                break
        else:
            pytest.skip("could not create new open report")
        bad = requests.post(f"{BASE}/api/admin/reports/{rid}/resolve",
                            json={"action": "banana"}, headers=_h(tokens["admin"]))
        assert bad.status_code == 400
        # clean up: dismiss
        requests.post(f"{BASE}/api/admin/reports/{rid}/resolve",
                      json={"action": "dismiss"}, headers=_h(tokens["admin"]))

    def test_remove_content_on_throwaway_post(self, tokens, ids):
        # artist creates a throwaway post
        r = requests.post(f"{BASE}/api/posts",
                          json={"kind": "update", "text": "REPORT TEST post iter16"},
                          headers=_h(tokens["a"]))
        assert r.status_code == 200, r.text
        post = r.json()
        pid = post["id"]
        # collector reports it
        rp = requests.post(f"{BASE}/api/reports",
                           json={"target_type": "post", "target_id": pid, "reason": "spam"},
                           headers=_h(tokens["c"]))
        assert rp.status_code == 200
        # admin finds & remove_content
        items = requests.get(f"{BASE}/api/admin/reports?status=open", headers=_h(tokens["admin"])).json()
        report = next((it for it in items if it["target_type"] == "post" and it["target_id"] == pid), None)
        assert report
        res = requests.post(f"{BASE}/api/admin/reports/{report['id']}/resolve",
                            json={"action": "remove_content"}, headers=_h(tokens["admin"]))
        assert res.status_code == 200
        # verify post is hidden from list
        lst = requests.get(f"{BASE}/api/posts?artist_id={ids['artist_id']}&limit=50", headers=UA).json()
        assert not any(p["id"] == pid for p in lst), "post still visible after remove_content"


def _uid(tok):
    return requests.get(f"{BASE}/api/auth/me", headers=_h(tok)).json()["id"]


# ------------- Recommendations ---------------
class TestRecommended:
    def test_unauth_401(self):
        r = requests.get(f"{BASE}/api/events/recommended", headers=UA)
        assert r.status_code in (401, 403)

    def test_recommended_ok(self, tokens, ids):
        r = requests.get(f"{BASE}/api/events/recommended", headers=_h(tokens["c"]))
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) <= 6
        if items:
            for e in items:
                assert isinstance(e.get("reason"), str) and e["reason"]
                assert isinstance(e.get("score"), (int, float))
            # one occurrence per series_id
            sids = [e.get("series_id") for e in items if e.get("series_id")]
            assert len(sids) == len(set(sids))
            # exclude events already RSVP'd
            rsvped = requests.get(f"{BASE}/api/events/mine/tickets?upcoming_only=false",
                                  headers=_h(tokens["c"])).json()
            rsvp_ids = {t["event"]["id"] for t in rsvped}
            for e in items:
                assert e["id"] not in rsvp_ids


# ------------- Host pages ---------------
class TestHostPage:
    def test_host_ok(self, tokens, ids):
        r = requests.get(f"{BASE}/api/events/hosts/{ids['artist_id']}", headers=_h(tokens["c"]))
        assert r.status_code == 200
        d = r.json()
        assert d["host"]["id"] == ids["artist_id"]
        assert "is_artist" in d["host"]
        for k in ("events", "upcoming", "attendees", "followers", "categories"):
            assert k in d["stats"]
        assert isinstance(d.get("is_following"), bool)
        assert isinstance(d.get("upcoming"), list)
        assert isinstance(d.get("past"), list)

    def test_host_unknown_404(self, tokens):
        r = requests.get(f"{BASE}/api/events/hosts/nonexistent-id", headers=_h(tokens["c"]))
        assert r.status_code == 404

    def test_follow_toggle_reflects(self, tokens, ids):
        aid = ids["artist_id"]
        # ensure a known state: unfollow then follow (restore following)
        requests.delete(f"{BASE}/api/users/{aid}/follow", headers=_h(tokens["c"]))
        d = requests.get(f"{BASE}/api/events/hosts/{aid}", headers=_h(tokens["c"])).json()
        assert d["is_following"] is False
        requests.post(f"{BASE}/api/users/{aid}/follow", headers=_h(tokens["c"]))
        d = requests.get(f"{BASE}/api/events/hosts/{aid}", headers=_h(tokens["c"])).json()
        assert d["is_following"] is True  # left following as required


# ------------- Thumbnails ---------------
class TestThumbnails:
    def test_thumb_serves_and_snaps(self, tokens):
        # find an event cover_image
        evs = requests.get(f"{BASE}/api/events?upcoming_only=false&limit=60", headers=UA).json()
        cover = next((e.get("cover_image") for e in evs if e.get("cover_image")), None)
        if not cover:
            pytest.skip("no event cover_image found")
        # full
        full = requests.get(f"{BASE}/api/files/{cover}", headers=UA)
        assert full.status_code == 200
        # 480 thumb
        t480 = requests.get(f"{BASE}/api/files/{cover}?w=480", headers=UA)
        assert t480.status_code == 200
        assert t480.headers.get("content-type", "").startswith("image/jpeg")
        assert "max-age" in (t480.headers.get("cache-control", "").lower())
        assert len(t480.content) < len(full.content) or full.headers.get("content-type", "").startswith("image/svg")
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(t480.content))
            assert im.width == 480, f"expected 480 got {im.width}"
        except ImportError:
            pass
        # snap 300 -> 240
        t300 = requests.get(f"{BASE}/api/files/{cover}?w=300", headers=UA)
        assert t300.status_code == 200
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(t300.content))
            assert im.width == 240
        except ImportError:
            pass
        # snap 5000 -> 960 (or smaller if original smaller)
        t5000 = requests.get(f"{BASE}/api/files/{cover}?w=5000", headers=UA)
        assert t5000.status_code == 200
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(t5000.content))
            assert im.width <= 960
        except ImportError:
            pass

    def test_thumb_unknown_404(self):
        r = requests.get(f"{BASE}/api/files/nope/nada.jpg?w=480", headers=UA)
        assert r.status_code == 404
