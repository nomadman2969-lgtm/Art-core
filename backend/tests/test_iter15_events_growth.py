"""Iteration 15 — Events discovery, saved events, share cards, badges, onboarding."""
import os
import re
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ArtCoreTest/1.0"}

DEMO_ARTIST = ("demo.artist@artcorestudio.net", "DemoArtist2026!")
DEMO_COLLECTOR = ("demo.collector@artcorestudio.net", "DemoCollector2026!")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, headers=UA, timeout=30)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    j = r.json()
    return j.get("token") or j.get("access_token"), j["user"]


@pytest.fixture(scope="module")
def collector():
    tok, u = _login(*DEMO_COLLECTOR)
    return {"token": tok, "user": u, "h": {**UA, "Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def artist():
    tok, u = _login(*DEMO_ARTIST)
    return {"token": tok, "user": u, "h": {**UA, "Authorization": f"Bearer {tok}"}}


# ---------- Categories ----------
def test_event_categories_13_items():
    r = requests.get(f"{BASE_URL}/api/events/meta/categories", headers=UA, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 13
    for item in data:
        assert set(item.keys()) >= {"key", "label", "color"}
    keys = {c["key"] for c in data}
    for k in ("exhibition", "street_art", "art_class", "museum", "auction", "virtual"):
        assert k in keys


# ---------- Search ----------
def test_search_neon():
    r = requests.get(f"{BASE_URL}/api/events?q=neon", headers=UA, timeout=30)
    assert r.status_code == 200
    events = r.json()
    titles = [e["title"] for e in events]
    assert any("Neon Rooftop" in t for t in titles), f"expected 'Neon Rooftop' in {titles}"
    # Tokyo Neon Night may be virtual — verify it's there (case-insensitive)
    assert any("neon" in t.lower() for t in titles)
    # Every returned event should match neon in some searchable field
    for e in events:
        blob = " ".join([
            e.get("title", ""), e.get("description", ""),
            (e.get("venue") or ""), (e.get("location") or {}).get("city", "") or "",
        ]).lower()
        assert "neon" in blob


def test_category_filter():
    r = requests.get(f"{BASE_URL}/api/events?category=street_art", headers=UA, timeout=30)
    assert r.status_code == 200
    for e in r.json():
        assert e["category"] == "street_art"
    r2 = requests.get(f"{BASE_URL}/api/events?category=bogus", headers=UA, timeout=30)
    assert r2.status_code == 400


def test_date_range_filter():
    now = datetime.now(timezone.utc)
    frm = now.isoformat()
    to = (now + timedelta(days=10)).isoformat()
    r = requests.get(f"{BASE_URL}/api/events", params={"date_from": frm, "date_to": to}, headers=UA, timeout=30)
    assert r.status_code == 200
    for e in r.json():
        assert frm <= e["start_at"] <= to


def test_free_only_filter():
    r = requests.get(f"{BASE_URL}/api/events?free_only=true", headers=UA, timeout=30)
    assert r.status_code == 200
    for e in r.json():
        assert e.get("is_free") is True


def test_trending_sort():
    r = requests.get(f"{BASE_URL}/api/events?sort=trending", headers=UA, timeout=30)
    assert r.status_code == 200
    events = r.json()
    assert len(events) > 0
    counts = [e.get("rsvp_count", 0) for e in events]
    assert counts == sorted(counts, reverse=True)
    # Neon Rooftop expected first per the review request
    assert "Neon Rooftop" in events[0]["title"]


def test_distance_sort_near_me():
    r = requests.get(
        f"{BASE_URL}/api/events",
        params={"near_lat": 40.7053, "near_lng": -73.9216, "radius_km": 30, "sort": "distance"},
        headers=UA, timeout=30,
    )
    assert r.status_code == 200
    events = r.json()
    assert len(events) > 0
    dists = [e["distance_km"] for e in events]
    for d in dists:
        assert d <= 30
    assert dists == sorted(dists)


def test_enriched_fields_and_saved_when_authed(collector):
    r = requests.get(f"{BASE_URL}/api/events", headers=collector["h"], timeout=30)
    assert r.status_code == 200
    events = r.json()
    assert len(events) > 0
    for e in events[:5]:
        assert "images" in e and isinstance(e["images"], list)
        assert "organizer" in e
        assert "saved_count" in e
        assert "saved" in e  # authed


# ---------- Save ----------
def _find_neon_rooftop_id():
    r = requests.get(f"{BASE_URL}/api/events?q=Neon Rooftop", headers=UA, timeout=30)
    assert r.status_code == 200
    for e in r.json():
        if "Neon Rooftop" in e["title"]:
            return e["id"]
    pytest.skip("Neon Rooftop event not found (seed missing)")


def test_save_toggle_full_flow(collector):
    eid = _find_neon_rooftop_id()
    # Save
    r = requests.post(f"{BASE_URL}/api/events/{eid}/save", headers=collector["h"], timeout=30)
    assert r.status_code == 200 and r.json() == {"saved": True}
    # my/saved contains it
    r = requests.get(f"{BASE_URL}/api/events/mine/saved", headers=collector["h"], timeout=30)
    assert r.status_code == 200
    assert any(e["id"] == eid for e in r.json())
    # saved_only=true only contains saved
    r = requests.get(f"{BASE_URL}/api/events?saved_only=true", headers=collector["h"], timeout=30)
    assert r.status_code == 200
    saved_ids = {e["id"] for e in r.json()}
    assert eid in saved_ids
    # unauth saved_only -> 401
    r = requests.get(f"{BASE_URL}/api/events?saved_only=true", headers=UA, timeout=30)
    assert r.status_code == 401
    # Toggle off (leave UNSAVED)
    r = requests.post(f"{BASE_URL}/api/events/{eid}/save", headers=collector["h"], timeout=30)
    assert r.status_code == 200 and r.json() == {"saved": False}
    # Verify state after
    r = requests.get(f"{BASE_URL}/api/events/{eid}", headers=collector["h"], timeout=30)
    assert r.status_code == 200 and r.json().get("saved") is False


def test_save_unknown_id_404(collector):
    r = requests.post(f"{BASE_URL}/api/events/nonexistent_id_xxx/save", headers=collector["h"], timeout=30)
    assert r.status_code == 404


# ---------- Create with new fields ----------
def test_create_event_with_new_fields_and_cleanup(artist):
    start = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    payload = {
        "title": "TEST_iter15 gallery night",
        "description": "TEST_iter15 event with all the new fields for validation.",
        "category": "street_art",
        "location": {"lat": 40.7, "lng": -73.9, "address": "x", "city": "Brooklyn"},
        "start_at": start,
        "venue": "TEST_Venue X",
        "organizer": "TEST_Organizer",
        "website": "example.org",  # no scheme -> https://
        "ticket_info": "Free entry, all welcome",
        "ticket_url": "example.org/tix",
        "tags": ["Murals", " opening "],
        "images": [],
        "is_free": True,
    }
    r = requests.post(f"{BASE_URL}/api/events", json=payload, headers=artist["h"], timeout=30)
    assert r.status_code == 200, r.text[:300]
    ev = r.json()
    eid = ev["id"]
    try:
        assert ev["venue"] == "TEST_Venue X"
        assert ev["organizer"] == "TEST_Organizer"
        assert ev["website"] == "https://example.org"
        assert ev["ticket_url"] == "https://example.org/tix"
        assert ev["ticket_info"] == "Free entry, all welcome"
        assert ev["tags"] == ["murals", "opening"]
        # GET returns same
        r2 = requests.get(f"{BASE_URL}/api/events/{eid}", headers=UA, timeout=30)
        assert r2.status_code == 200
        got = r2.json()
        assert got["venue"] == "TEST_Venue X"
        assert got["website"] == "https://example.org"
        assert got["tags"] == ["murals", "opening"]
        # PATCH
        r3 = requests.patch(f"{BASE_URL}/api/events/{eid}", json={"venue": "New venue", "tags": ["a"]}, headers=artist["h"], timeout=30)
        assert r3.status_code == 200
        r4 = requests.get(f"{BASE_URL}/api/events/{eid}", headers=UA, timeout=30)
        assert r4.json()["venue"] == "New venue"
        assert r4.json()["tags"] == ["a"]
    finally:
        # cleanup
        requests.delete(f"{BASE_URL}/api/events/{eid}", headers=artist["h"], timeout=30)


def test_create_accepts_new_categories(artist):
    """exhibition / art_class / museum / auction should all be accepted."""
    start = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    ids = []
    try:
        for cat in ("exhibition", "art_class", "museum", "auction"):
            payload = {
                "title": f"TEST_iter15 cat {cat}",
                "description": "TEST_iter15 category acceptance",
                "category": cat,
                "location": {"lat": 40.7, "lng": -73.9, "city": "Brooklyn"},
                "start_at": start,
                "is_free": True,
            }
            r = requests.post(f"{BASE_URL}/api/events", json=payload, headers=artist["h"], timeout=30)
            assert r.status_code == 200, f"{cat} rejected: {r.text[:200]}"
            ids.append(r.json()["id"])
    finally:
        for eid in ids:
            requests.delete(f"{BASE_URL}/api/events/{eid}", headers=artist["h"], timeout=30)


# ---------- Share cards ----------
def test_share_event_html_and_png():
    eid = _find_neon_rooftop_id()
    r = requests.get(f"{BASE_URL}/api/share/event/{eid}", headers=UA, timeout=30, allow_redirects=False)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    html = r.text
    assert "og:title" in html
    assert f"/api/share/og/event/{eid}.png" in html
    assert 'twitter:card" content="summary_large_image"' in html
    # meta refresh to /events/{id}
    assert re.search(rf'http-equiv="refresh"[^>]*/events/{eid}', html)
    # png
    p = requests.get(f"{BASE_URL}/api/share/og/event/{eid}.png", headers=UA, timeout=60)
    assert p.status_code == 200
    assert p.headers.get("content-type", "").startswith("image/png")
    assert p.content[:4] == b"\x89PNG"


def test_share_artwork_and_studio():
    # Grab an artwork
    r = requests.get(f"{BASE_URL}/api/artworks?limit=1", headers=UA, timeout=30)
    assert r.status_code == 200
    arts = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    if not arts:
        pytest.skip("no artworks")
    aid = arts[0]["id"]
    r = requests.get(f"{BASE_URL}/api/share/artwork/{aid}", headers=UA, timeout=30)
    assert r.status_code == 200 and "og:title" in r.text
    p = requests.get(f"{BASE_URL}/api/share/og/artwork/{aid}.png", headers=UA, timeout=60)
    assert p.status_code == 200 and p.headers["content-type"].startswith("image/png")
    # Studio (demo artist)
    _, u = _login(*DEMO_ARTIST)
    uid = u["id"]
    r = requests.get(f"{BASE_URL}/api/share/studio/{uid}", headers=UA, timeout=30)
    assert r.status_code == 200 and "og:title" in r.text
    p = requests.get(f"{BASE_URL}/api/share/og/studio/{uid}.png", headers=UA, timeout=60)
    assert p.status_code == 200 and p.headers["content-type"].startswith("image/png")


def test_share_unknown_ids_404():
    for path in ("share/event/nope", "share/og/event/nope.png",
                 "share/artwork/nope", "share/og/artwork/nope.png",
                 "share/studio/nope", "share/og/studio/nope.png"):
        r = requests.get(f"{BASE_URL}/api/{path}", headers=UA, timeout=30)
        assert r.status_code == 404, f"{path} -> {r.status_code}"


# ---------- Badges ----------
def test_demo_artist_badges(artist):
    uid = artist["user"]["id"]
    r = requests.get(f"{BASE_URL}/api/users/{uid}/badges", headers=UA, timeout=30)
    assert r.status_code == 200
    badges = r.json()
    assert len(badges) == 9
    for b in badges:
        assert set(b.keys()) >= {"id", "label", "desc", "color", "earned"}
    earned_ids = {b["id"] for b in badges if b["earned"]}
    for want in ("first_sale", "auction_closer", "commissioned", "event_host", "sold_out_show"):
        assert want in earned_ids, f"demo artist missing earned badge {want}: {earned_ids}"


# ---------- Onboarding ----------
def test_onboarding_complete_flow():
    # Register a new artist
    ts = int(datetime.now(timezone.utc).timestamp())
    email = f"onboard_test_{ts}@example.com"
    reg = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "OnboardTest2026!", "name": "Onboard Tester", "role": "artist",
    }, headers=UA, timeout=30)
    assert reg.status_code in (200, 201), reg.text[:200]
    tok = reg.json().get("token") or reg.json().get("access_token")
    if not tok:
        # Fallback login
        tok, _ = _login(email, "OnboardTest2026!")
    h = {**UA, "Authorization": f"Bearer {tok}"}
    # Unauthed 401
    ua = requests.post(f"{BASE_URL}/api/onboarding/complete", headers=UA, timeout=30)
    assert ua.status_code == 401
    # Authed OK
    r = requests.post(f"{BASE_URL}/api/onboarding/complete", headers=h, timeout=30)
    assert r.status_code == 200 and r.json() == {"ok": True}
    # /me reflects
    me = requests.get(f"{BASE_URL}/api/auth/me", headers=h, timeout=30)
    assert me.status_code == 200 and me.json().get("onboarded") is True
