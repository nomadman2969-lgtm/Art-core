"""Iteration 17 backend tests: follow alerts, staff picks, calendar feed."""
import os
import time
import pytest
import requests

def _read_env(key: str) -> str:
    v = os.environ.get(key)
    if v:
        return v
    for p in ("/app/frontend/.env", "/app/backend/.env"):
        try:
            for line in open(p):
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
        except FileNotFoundError:
            pass
    raise KeyError(key)


BASE = _read_env("REACT_APP_BACKEND_URL").rstrip("/")
UA = {"User-Agent": "Mozilla/5.0 ArtCoreTests"}


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, headers=UA, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def collector_token():
    return _login("demo.collector@artcorestudio.net", "DemoCollector2026!")


@pytest.fixture(scope="module")
def artist_token():
    return _login("demo.artist@artcorestudio.net", "DemoArtist2026!")


@pytest.fixture(scope="module")
def admin_token():
    return _login("monster@houseofmonster.com", "MonsterAdmin2026!")


def _auth(t):
    return {"Authorization": f"Bearer {t}", **UA}


# ---------- Follow alerts ----------
class TestFollowAlerts:
    def test_post_triggers_followed_new_post(self, artist_token, collector_token):
        # ensure collector follows artist (idempotent)
        me_artist = requests.get(f"{BASE}/api/auth/me", headers=_auth(artist_token)).json()
        artist_id = me_artist["id"]
        requests.post(f"{BASE}/api/users/{artist_id}/follow", headers=_auth(collector_token))

        r = requests.post(f"{BASE}/api/posts", headers=_auth(artist_token),
                          json={"kind": "update", "text": "ITER17 follow alert"})
        assert r.status_code in (200, 201), r.text
        post_id = r.json().get("id")
        assert post_id
        time.sleep(2.5)
        notifs = requests.get(f"{BASE}/api/notifications", headers=_auth(collector_token)).json()
        items = notifs if isinstance(notifs, list) else (notifs.get("items") or notifs.get("notifications") or [])
        match = [n for n in items if n.get("kind") == "followed_new_post" and n.get("post_id") == post_id]
        assert match, f"no followed_new_post for post_id={post_id}. sample: {items[:3]}"
        n = match[0]
        assert "ITER17" in (n.get("preview") or n.get("body") or "")
        # cleanup
        d = requests.delete(f"{BASE}/api/posts/{post_id}", headers=_auth(artist_token))
        assert d.status_code in (200, 204)

    def test_event_triggers_followed_new_event(self, artist_token, collector_token):
        from datetime import datetime, timedelta, timezone
        start = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        payload = {"title": "ITER17 alert event", "start_at": start,
                   "location": {"lat": 40.7, "lng": -73.9, "address": "NY", "city": "New York"},
                   "category": "exhibition", "description": "test"}
        r = requests.post(f"{BASE}/api/events", headers=_auth(artist_token), json=payload)
        assert r.status_code in (200, 201), r.text
        eid = r.json().get("id")
        assert eid
        time.sleep(2.5)
        notifs = requests.get(f"{BASE}/api/notifications", headers=_auth(collector_token)).json()
        items = notifs if isinstance(notifs, list) else (notifs.get("items") or notifs.get("notifications") or [])
        match = [n for n in items if n.get("kind") == "followed_new_event" and n.get("event_id") == eid]
        assert match, f"no followed_new_event for eid={eid}"
        assert match[0].get("event_title") == "ITER17 alert event" or "ITER17" in (match[0].get("event_title") or "")
        # cleanup
        d = requests.delete(f"{BASE}/api/events/{eid}", headers=_auth(artist_token))
        assert d.status_code in (200, 204)


# ---------- Staff Picks ----------
class TestStaffPicks:
    def test_public_get(self):
        r = requests.get(f"{BASE}/api/staff-picks", headers=UA)
        assert r.status_code == 200
        d = r.json()
        for k in ("title", "blurb", "updated_at", "artworks", "events"):
            assert k in d
        assert len(d["artworks"]) >= 1
        assert d["artworks"][0].get("artist", {}).get("name")

    def test_non_admin_forbidden(self, collector_token):
        r = requests.put(f"{BASE}/api/admin/staff-picks", headers=_auth(collector_token),
                         json={"title": "x", "artwork_ids": [], "event_ids": []})
        assert r.status_code == 403

    def test_admin_update_and_restore(self, admin_token):
        # snapshot original
        orig = requests.get(f"{BASE}/api/staff-picks", headers=UA).json()
        orig_art_ids = [a["id"] for a in orig["artworks"]]
        orig_ev_ids = [e["id"] for e in orig["events"]]
        assert len(orig_art_ids) == 3
        assert len(orig_ev_ids) == 1

        # write new
        new_payload = {"title": "ITER17 Picks", "blurb": "x",
                       "artwork_ids": orig_art_ids + ["nonexistent-xyz"],
                       "event_ids": orig_ev_ids}
        r = requests.put(f"{BASE}/api/admin/staff-picks", headers=_auth(admin_token), json=new_payload)
        assert r.status_code == 200

        got = requests.get(f"{BASE}/api/staff-picks", headers=UA).json()
        assert got["title"] == "ITER17 Picks"
        assert [a["id"] for a in got["artworks"]] == orig_art_ids  # order preserved, invalid dropped

        # 12-truncation check
        r2 = requests.put(f"{BASE}/api/admin/staff-picks", headers=_auth(admin_token),
                          json={"title": "ITER17 Picks", "blurb": "x",
                                "artwork_ids": orig_art_ids * 10, "event_ids": orig_ev_ids})
        assert r2.status_code == 200
        got2 = requests.get(f"{BASE}/api/staff-picks", headers=UA).json()
        assert len(got2["artworks"]) <= 12

        # restore
        restore = {"title": "Staff Picks · This Week",
                   "blurb": "Neon, chrome and one very good rooftop.",
                   "artwork_ids": orig_art_ids, "event_ids": orig_ev_ids}
        rr = requests.put(f"{BASE}/api/admin/staff-picks", headers=_auth(admin_token), json=restore)
        assert rr.status_code == 200
        final = requests.get(f"{BASE}/api/staff-picks", headers=UA).json()
        assert final["title"] == "Staff Picks · This Week"
        assert [a["id"] for a in final["artworks"]] == orig_art_ids
        assert [e["id"] for e in final["events"]] == orig_ev_ids


# ---------- Calendar ----------
class TestCalendar:
    def test_unauth_401(self):
        r = requests.post(f"{BASE}/api/calendar/token", headers=UA)
        assert r.status_code == 401

    def test_token_flow(self, collector_token):
        r = requests.post(f"{BASE}/api/calendar/token", headers=_auth(collector_token))
        assert r.status_code == 200
        d = r.json()
        assert d["token"] and d["url"].startswith("https://") and "/api/calendar/" in d["url"]
        assert d["webcal_url"].startswith("webcal://")
        assert d["google_url"].startswith("https://calendar.google.com/calendar/r?cid=webcal://")
        tok1 = d["token"]

        # idempotent
        r2 = requests.post(f"{BASE}/api/calendar/token", headers=_auth(collector_token))
        assert r2.json()["token"] == tok1

        # save an event that's not RSVP'd — find Roma Norte or any upcoming
        events = requests.get(f"{BASE}/api/events?limit=50", headers=_auth(collector_token)).json()
        ev_list = events if isinstance(events, list) else (events.get("items") or [])
        target = None
        for e in ev_list:
            if "Roma Norte" in (e.get("title") or ""):
                target = e
                break
        if not target and ev_list:
            target = ev_list[0]
        saved_id = None
        if target:
            sv = requests.post(f"{BASE}/api/events/{target['id']}/save", headers=_auth(collector_token))
            if sv.status_code in (200, 201):
                saved_id = target["id"]

        # fetch ICS
        ics_r = requests.get(d["url"], headers=UA)
        assert ics_r.status_code == 200
        assert "text/calendar" in ics_r.headers.get("content-type", "")
        body = ics_r.text
        assert "BEGIN:VCALENDAR" in body
        assert "Demo Collector" in body
        vevent_count = body.count("BEGIN:VEVENT")
        assert vevent_count >= 3, f"only {vevent_count} VEVENTs"
        # SUMMARY endings
        summaries = [ln for ln in body.splitlines() if ln.startswith("SUMMARY:")]
        assert all(s.endswith("(Going)") or s.endswith("(Saved)") for s in summaries), summaries[:5]
        assert "TRIGGER:-PT24H" in body
        assert "URL:" in body
        assert "UID:" in body
        if saved_id:
            assert "(Saved)" in body

        # unsave
        if saved_id:
            requests.delete(f"{BASE}/api/events/{saved_id}/save", headers=_auth(collector_token))

        # reset
        rd = requests.delete(f"{BASE}/api/calendar/token", headers=_auth(collector_token))
        assert rd.status_code == 200
        gone = requests.get(d["url"], headers=UA)
        assert gone.status_code == 404
        r3 = requests.post(f"{BASE}/api/calendar/token", headers=_auth(collector_token))
        assert r3.json()["token"] != tok1

    def test_bad_token_404(self):
        r = requests.get(f"{BASE}/api/calendar/does-not-exist.ics", headers=UA)
        assert r.status_code == 404
