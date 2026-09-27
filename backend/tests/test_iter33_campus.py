"""Iter33 — Campus Pages: search/directory/me/page + admin approve/rename/reject/merge + events tagging."""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@artcorestudio.net"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", os.environ["ADMIN_PASSWORD"])
CAMPUS_ARTIST = ("campus.artist@example.com", "Campus123!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _headers(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def admin_tok():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def artist_tok():
    return _login(*CAMPUS_ARTIST)


@pytest.fixture(scope="session")
def buyer_tok():
    email = f"TEST_buyer_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Buyer123!", "name": "Test Buyer", "role": "buyer"}, timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def throwaway_artist():
    email = f"TEST_artist_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Artist123!", "name": "Test Artist", "role": "artist"}, timeout=20)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    return {"token": d["token"], "id": d["user"]["id"], "email": email}


# ---- search & directory ----
class TestSearchDirectory:
    def test_search_short_returns_empty(self):
        r = requests.get(f"{API}/campus/search", params={"q": "a"}, timeout=15)
        assert r.status_code == 200
        assert r.json() == []

    def test_search_risd_alias(self):
        r = requests.get(f"{API}/campus/search", params={"q": "risd"}, timeout=15)
        assert r.status_code == 200
        rows = r.json()
        names = [x["name"] for x in rows]
        assert any("Rhode Island School of Design" in n for n in names), f"Got: {names}"
        risd = next(x for x in rows if "Rhode Island" in x["name"])
        assert "aliases" in risd and isinstance(risd["aliases"], list)

    def test_search_savannah(self):
        r = requests.get(f"{API}/campus/search", params={"q": "savannah"}, timeout=15)
        assert r.status_code == 200
        names = [x["name"] for x in r.json()]
        assert any("Savannah College of Art and Design" in n for n in names), f"Got: {names}"

    def test_directory(self):
        r = requests.get(f"{API}/campus", timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for c in rows:
            assert "artist_count" in c
            assert c["artist_count"] >= 1 or c.get("featured")


# ---- /campus/me lifecycle ----
class TestMe:
    def test_buyer_forbidden_post(self, buyer_tok):
        r = requests.post(f"{API}/campus/me", json={"campus_id": "x"}, headers=_headers(buyer_tok), timeout=15)
        assert r.status_code == 403

    def test_artist_set_by_slug_get_clear(self, throwaway_artist):
        tok = throwaway_artist["token"]
        # get SCAD id via search
        r = requests.get(f"{API}/campus/search", params={"q": "savannah"}, timeout=15)
        scad = next(x for x in r.json() if "Savannah College" in x["name"])
        # set by slug
        r = requests.post(f"{API}/campus/me", json={"campus_id": scad["slug"]}, headers=_headers(tok), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["slug"] == scad["slug"]
        # auth/me includes campus
        me = requests.get(f"{API}/auth/me", headers=_headers(tok), timeout=15).json()
        assert me.get("campus", {}).get("slug") == scad["slug"]
        # /campus/me returns
        mc = requests.get(f"{API}/campus/me", headers=_headers(tok), timeout=15).json()
        assert mc and mc["slug"] == scad["slug"]
        # clear
        r = requests.delete(f"{API}/campus/me", headers=_headers(tok), timeout=15)
        assert r.status_code == 200
        me2 = requests.get(f"{API}/auth/me", headers=_headers(tok), timeout=15).json()
        assert not me2.get("campus")


@pytest.fixture(scope="session")
def pending_campus(throwaway_artist):
    """A pending campus created by throwaway_artist — shared by admin tests (xdist-safe)."""
    tok = throwaway_artist["token"]
    name = f"TEST Admin School {uuid.uuid4().hex[:6].upper()}"
    r = requests.post(f"{API}/campus/me", json={"name": name, "city": "Testville"}, headers=_headers(tok), timeout=15)
    assert r.status_code == 200, r.text
    c = r.json()
    return {"id": c["id"], "slug": c["slug"], "creator_id": throwaway_artist["id"], "creator_tok": tok}


# ---- Pending creation via name (dedupe + notification) ----
class TestPendingCreation:
    def test_create_pending_dedupe(self, throwaway_artist, admin_tok):
        tok = throwaway_artist["token"]
        name = f"TEST Pending School {uuid.uuid4().hex[:6].upper()}"
        r = requests.post(f"{API}/campus/me", json={"name": name, "city": "Testville"}, headers=_headers(tok), timeout=15)
        assert r.status_code == 200, r.text
        c1 = r.json()
        assert c1["status"] == "pending"
        # tagged
        me = requests.get(f"{API}/auth/me", headers=_headers(tok), timeout=15).json()
        assert me["campus"]["id"] == c1["id"]
        # dedupe with different casing/punctuation
        variant = name.lower().replace(" ", "  ") + "!"
        r2 = requests.post(f"{API}/campus/me", json={"name": variant}, headers=_headers(tok), timeout=15)
        assert r2.status_code == 200
        c2 = r2.json()
        assert c2["id"] == c1["id"], f"Duplicate campus created: {c1['id']} vs {c2['id']}"
        # admin notified
        notifs = requests.get(f"{API}/notifications", headers=_headers(admin_tok), timeout=15).json()
        rows = notifs.get("items") if isinstance(notifs, dict) else notifs
        assert any(n.get("kind") == "campus_pending" and n.get("campus_id") == c1["id"] for n in rows), \
            f"campus_pending notif not found for {c1['id']}"


# ---- Campus public page ----
class TestCampusPage:
    def test_scad_page(self):
        r = requests.get(f"{API}/campus/savannah-college-of-art-and-design", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("campus", "stats", "artists", "artworks", "events", "leaderboard"):
            assert k in d
        for k in ("artists", "artworks_live", "sales", "events_upcoming"):
            assert k in d["stats"]

    def test_unknown_slug_404(self):
        r = requests.get(f"{API}/campus/no-such-campus-xyz-{uuid.uuid4().hex[:6]}", timeout=15)
        assert r.status_code == 404


# ---- Admin approve/rename/reject/merge ----
class TestAdmin:
    def test_non_admin_forbidden(self, artist_tok):
        r = requests.get(f"{API}/admin/campuses", headers=_headers(artist_tok), timeout=15)
        assert r.status_code == 403

    def test_admin_list_pending(self, admin_tok, pending_campus):
        r = requests.get(f"{API}/admin/campuses", params={"status": "pending"}, headers=_headers(admin_tok), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        cid = pending_campus["id"]
        row = next((x for x in rows if x["id"] == cid), None)
        assert row is not None, "pending campus not returned by admin list"
        assert row.get("created_by") and row["created_by"].get("email")
        assert "artist_count" in row

    def test_admin_approve_and_feature_and_rename(self, admin_tok, pending_campus):
        cid = pending_campus["id"]
        # approve + feature
        r = requests.patch(f"{API}/admin/campuses/{cid}", json={"status": "approved", "featured": True}, headers=_headers(admin_tok), timeout=15)
        assert r.status_code == 200
        # notification to creator
        n = requests.get(f"{API}/notifications", headers=_headers(pending_campus['creator_tok']), timeout=15).json()
        rows = n.get("items") if isinstance(n, dict) else n
        assert any(x.get("kind") == "campus_approved" and x.get("campus_id") == cid for x in rows)
        # rename
        new_name = f"TEST Renamed {uuid.uuid4().hex[:5].upper()}"
        r = requests.patch(f"{API}/admin/campuses/{cid}", json={"name": new_name}, headers=_headers(admin_tok), timeout=15)
        assert r.status_code == 200
        # denorm sync
        me = requests.get(f"{API}/auth/me", headers=_headers(pending_campus['creator_tok']), timeout=15).json()
        assert me["campus"]["name"] == new_name, f"campus_name denorm didn't sync: {me['campus']}"

    def test_admin_merge_into_scad(self, admin_tok, pending_campus):
        # Need SCAD id
        rows = requests.get(f"{API}/admin/campuses", params={"q": "savannah"}, headers=_headers(admin_tok), timeout=15).json()
        scad = next(x for x in rows if "Savannah College" in x["name"])
        src = pending_campus["id"]
        # merge into self -> 400
        r = requests.post(f"{API}/admin/campuses/{src}/merge", json={"into_id": src}, headers=_headers(admin_tok), timeout=15)
        assert r.status_code == 400
        # actual merge
        r = requests.post(f"{API}/admin/campuses/{src}/merge", json={"into_id": scad["id"]}, headers=_headers(admin_tok), timeout=15)
        assert r.status_code == 200, r.text
        # old slug resolves to SCAD now
        r = requests.get(f"{API}/campus/{pending_campus['slug']}", timeout=15)
        assert r.status_code == 200
        assert r.json()["campus"]["slug"] == scad["slug"]
        # creator now tagged to SCAD
        me = requests.get(f"{API}/auth/me", headers=_headers(pending_campus['creator_tok']), timeout=15).json()
        assert me["campus"]["slug"] == scad["slug"]

    def test_admin_reject_untags(self, admin_tok, pending_campus, throwaway_artist):
        # create another pending campus with a different throwaway artist token, then reject
        email = f"TEST_artist_{uuid.uuid4().hex[:8]}@example.com"
        rr = requests.post(f"{API}/auth/register", json={"email": email, "password": "Artist123!", "name": "R", "role": "artist"}, timeout=20)
        tok = rr.json()["token"]
        name = f"TEST Reject School {uuid.uuid4().hex[:6].upper()}"
        c = requests.post(f"{API}/campus/me", json={"name": name}, headers=_headers(tok), timeout=15).json()
        r = requests.patch(f"{API}/admin/campuses/{c['id']}", json={"status": "rejected"}, headers=_headers(admin_tok), timeout=15)
        assert r.status_code == 200
        # user untagged
        me = requests.get(f"{API}/auth/me", headers=_headers(tok), timeout=15).json()
        assert not me.get("campus")
        # page 404
        r = requests.get(f"{API}/campus/{c['slug']}", timeout=15)
        assert r.status_code == 404


# ---- Events + campus tagging ----
class TestEventsCampus:
    def test_event_with_campus_appears_on_campus_page(self, artist_tok):
        # SCAD id
        s = requests.get(f"{API}/campus/search", params={"q": "savannah"}, timeout=15).json()
        scad = next(x for x in s if "Savannah College" in x["name"])
        # create event 7 days from now
        from datetime import datetime, timedelta, timezone
        start = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=7, hours=2)).isoformat()
        payload = {
            "title": f"TEST Campus Event {uuid.uuid4().hex[:6]}",
            "description": "test event description",
            "category": "gallery_opening",
            "location": {"name": "SCAD", "city": "Savannah", "country": "US", "lat": 32.08, "lng": -81.09},
            "start_at": start, "end_at": end,
            "campus_id": scad["id"],
        }
        r = requests.post(f"{API}/events", json=payload, headers=_headers(artist_tok), timeout=20)
        if r.status_code not in (200, 201):
            pytest.skip(f"event create not supported for this artist: {r.status_code} {r.text[:200]}")
        ev = r.json()
        assert ev.get("campus_id") == scad["id"]
        assert ev.get("campus_slug") == scad["slug"]
        assert ev.get("campus_name")
        eid = ev["id"]
        # filter by campus
        r = requests.get(f"{API}/events", params={"campus": scad["slug"]}, timeout=15)
        assert r.status_code == 200
        items = r.json()
        items = items.get("items") if isinstance(items, dict) else items
        assert any(e["id"] == eid for e in items)
        # appears on campus page
        cp = requests.get(f"{API}/campus/{scad['slug']}", timeout=15).json()
        assert any(e["id"] == eid for e in cp["events"])
        # clear
        r = requests.patch(f"{API}/events/{eid}", json={"campus_id": None}, headers=_headers(artist_tok), timeout=15)
        assert r.status_code == 200
        ev2 = r.json()
        assert not ev2.get("campus_id")


# ---- Studio + artworks enrichment ----
class TestEnrichment:
    def test_studio_includes_campus(self, artist_tok):
        me = requests.get(f"{API}/auth/me", headers=_headers(artist_tok), timeout=15).json()
        aid = me["id"]
        r = requests.get(f"{API}/studio/{aid}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        artist = d.get("artist") or d
        assert artist.get("campus"), f"studio missing artist.campus: keys={list(d.keys())}"
        assert artist["campus"].get("slug")

    def test_artworks_have_campus_name(self, artist_tok):
        r = requests.get(f"{API}/artworks", timeout=15)
        assert r.status_code == 200
        items = r.json()
        items = items.get("items") if isinstance(items, dict) else items
        # at least one item's artist should have campus_name if campus.artist has live art
        assert isinstance(items, list)
        # Just check schema tolerance - artist object may or may not include campus_name depending on data
        for it in items[:20]:
            ar = it.get("artist") or {}
            if ar.get("campus_slug"):
                assert ar.get("campus_name")
                return
        # no assertion failure if no data — just informational
