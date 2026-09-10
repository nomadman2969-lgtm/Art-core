"""Iteration 18: Upcycle section - backend tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api"

DEMO_ARTIST_EMAIL = "demo.artist@artcorestudio.net"
DEMO_ARTIST_PW = "DemoArtist2026!"


@pytest.fixture(scope="module")
def artist_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    r = s.post(f"{API}/auth/login", json={"email": DEMO_ARTIST_EMAIL, "password": DEMO_ARTIST_PW}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def anon_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    return s


# ---------------------- meta ----------------------
def test_upcycle_meta(anon_session):
    r = anon_session.get(f"{API}/upcycle/meta", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 5
    types = data["types"]
    assert len(types) == 9
    by_key = {t["key"]: t for t in types}
    for k in ["chair", "table", "dresser", "cabinet", "lamp"]:
        assert by_key[k]["count"] == 1, f"{k} count = {by_key[k]['count']}"
    for k in ["mirror", "shelf", "bench", "other"]:
        assert by_key[k]["count"] == 0
    for t in types:
        assert "label" in t and "key" in t


# ---------------------- list filters ----------------------
def test_list_section_upcycle(anon_session):
    r = anon_session.get(f"{API}/artworks", params={"section": "upcycle"}, timeout=15)
    assert r.status_code == 200
    payload = r.json()
    items = payload if isinstance(payload, list) else payload.get("items", payload.get("artworks", []))
    assert len(items) == 5
    for it in items:
        assert it.get("section") == "upcycle"
        assert it.get("furniture_type")
        assert it.get("materials")
        assert isinstance(it.get("before_image"), str) and it["before_image"]
        assert it.get("artist", {}).get("name")


def test_list_upcycle_chair(anon_session):
    r = anon_session.get(f"{API}/artworks", params={"section": "upcycle", "furniture_type": "chair"}, timeout=15)
    assert r.status_code == 200
    payload = r.json()
    items = payload if isinstance(payload, list) else payload.get("items", payload.get("artworks", []))
    assert len(items) == 1
    assert items[0]["title"] == "Throne No. 3"


def test_list_section_art_excludes_upcycle(anon_session):
    r = anon_session.get(f"{API}/artworks", params={"section": "art", "limit": 200}, timeout=15)
    assert r.status_code == 200
    payload = r.json()
    items = payload if isinstance(payload, list) else payload.get("items", payload.get("artworks", []))
    for it in items:
        assert it.get("section") != "upcycle"


def test_list_default_includes_both(anon_session):
    r = anon_session.get(f"{API}/artworks", params={"limit": 500}, timeout=15)
    assert r.status_code == 200
    payload = r.json()
    items = payload if isinstance(payload, list) else payload.get("items", payload.get("artworks", []))
    sections = {it.get("section") for it in items}
    assert "upcycle" in sections
    # non-upcycle can be "art" or legacy None
    assert any(s != "upcycle" for s in sections)


def test_list_upcycle_sort(anon_session):
    ra = anon_session.get(f"{API}/artworks", params={"section": "upcycle", "sort": "price_asc"}, timeout=15).json()
    rd = anon_session.get(f"{API}/artworks", params={"section": "upcycle", "sort": "price_desc"}, timeout=15).json()
    a_items = ra if isinstance(ra, list) else ra.get("items", ra.get("artworks", []))
    d_items = rd if isinstance(rd, list) else rd.get("items", rd.get("artworks", []))
    a_prices = [i.get("price", 0) for i in a_items]
    d_prices = [i.get("price", 0) for i in d_items]
    assert a_prices == sorted(a_prices)
    assert d_prices == sorted(d_prices, reverse=True)


# ---------------------- create validation ----------------------
def _base_payload(**over):
    p = {
        "title": "ITER18 lamp",
        "description": "iter18 test",
        "medium": "Mixed Media",
        "price": 100,
        "width_in": 10,
        "height_in": 20,
        "images": ["uploads/placeholder.jpg"],
        "section": "upcycle",
        "furniture_type": "lamp",
        "materials": "x",
    }
    p.update(over)
    return p


created_ids = []


def test_create_upcycle_ok(artist_session):
    r = artist_session.post(f"{API}/artworks", json=_base_payload(), timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("section") == "upcycle"
    assert data.get("furniture_type") == "lamp"
    assert data.get("status") == "pending_fee"
    created_ids.append(data.get("id") or data.get("_id"))


def test_create_bad_section(artist_session):
    r = artist_session.post(f"{API}/artworks", json=_base_payload(section="bogus"), timeout=20)
    assert r.status_code == 422, r.status_code


def test_create_bad_furniture_type(artist_session):
    r = artist_session.post(f"{API}/artworks", json=_base_payload(furniture_type="sofa"), timeout=20)
    assert r.status_code == 422, r.status_code


def test_create_default_section_art(artist_session):
    p = _base_payload(title="ITER18 default")
    p.pop("section")
    p.pop("furniture_type")
    p.pop("materials")
    r = artist_session.post(f"{API}/artworks", json=p, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("section") == "art"
    created_ids.append(data.get("id") or data.get("_id"))


def test_cleanup(artist_session):
    for aid in created_ids:
        if not aid:
            continue
        r = artist_session.delete(f"{API}/artworks/{aid}", timeout=15)
        assert r.status_code in (200, 204, 404), f"delete {aid}: {r.status_code} {r.text}"


# ---------------------- iter18 spec additions ----------------------
def test_settings_commission_3pct(anon_session):
    r = anon_session.get(f"{API}/settings", timeout=15)
    assert r.status_code == 200, r.text
    assert float(r.json()["commission_percent"]) == 3.0


def _items(r):
    p = r.json()
    return p if isinstance(p, list) else p.get("items", p.get("artworks", []))


def test_list_upcycle_pickup_only(anon_session):
    r = anon_session.get(f"{API}/artworks", params={"section": "upcycle", "pickup_only": "true"}, timeout=15)
    assert r.status_code == 200
    items = _items(r)
    assert len(items) == 4, f"expected 4, got {len(items)} titles={[i['title'] for i in items]}"
    titles = {i["title"] for i in items}
    assert "Koi Lantern" not in titles


def test_list_upcycle_near_small_radius(anon_session):
    r = anon_session.get(f"{API}/artworks", params={"section": "upcycle", "near_lat": 40.7, "near_lng": -73.9, "radius_km": 100}, timeout=15)
    assert r.status_code == 200
    items = _items(r)
    assert len(items) == 1
    assert items[0]["title"] == "Throne No. 3"
    assert items[0].get("distance_km") is not None
    assert items[0]["distance_km"] <= 5


def test_list_upcycle_near_global_radius(anon_session):
    r = anon_session.get(f"{API}/artworks", params={"section": "upcycle", "near_lat": 40.7, "near_lng": -73.9, "radius_km": 20000}, timeout=15)
    assert r.status_code == 200
    items = _items(r)
    assert len(items) == 5
    dists = [i["distance_km"] for i in items]
    assert dists == sorted(dists), f"not ascending: {dists}"
    assert items[0]["title"] == "Throne No. 3"


def test_create_full_upcycle_payload_and_cleanup(artist_session):
    payload = {
        "title": "ITER18 Upcycle Chair",
        "description": "iter18 upcycle chair test",
        "medium": "Mixed Media",
        "price": 120,
        "width_in": 20,
        "height_in": 30,
        "images": ["uploads/placeholder.jpg"],
        "section": "upcycle",
        "furniture_type": "bench",
        "materials": "pine, acrylic",
        "delivery": ["local_pickup"],
        "location": {"lat": 40.7, "lng": -73.9, "city": "Brooklyn, NY"},
    }
    r = artist_session.post(f"{API}/artworks", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["section"] == "upcycle"
    assert d["furniture_type"] == "bench"
    assert d["materials"] == "pine, acrylic"
    assert d["delivery"] == ["local_pickup"]
    assert d["location"]["city"] == "Brooklyn, NY"
    assert d["status"] == "pending_fee"
    aid = d.get("id") or d.get("_id")
    assert aid
    # cleanup immediately
    dr = artist_session.delete(f"{API}/artworks/{aid}", timeout=15)
    assert dr.status_code in (200, 204)


def test_create_delivery_bogus_coerced(artist_session):
    payload = _base_payload(title="ITER18 delivery coerce", delivery=["bogus"])
    r = artist_session.post(f"{API}/artworks", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["delivery"] == ["ships"], f"got {d.get('delivery')}"
    aid = d.get("id") or d.get("_id")
    if aid:
        artist_session.delete(f"{API}/artworks/{aid}", timeout=15)


def test_event_analytics_platform_fee_3pct(artist_session, anon_session):
    # find the Neon Rooftop event
    r = anon_session.get(f"{API}/events", params={"limit": 200}, timeout=15)
    assert r.status_code == 200
    payload = r.json()
    events = payload if isinstance(payload, list) else payload.get("items", payload.get("events", []))
    target = None
    for e in events:
        if e.get("slug") == "ev-neon-rooftop" or "Neon Rooftop" in (e.get("title") or ""):
            target = e
            break
    assert target, "Neon Rooftop event not found"
    eid = target.get("id") or target.get("_id")
    ar = artist_session.get(f"{API}/events/{eid}/analytics", timeout=20)
    assert ar.status_code == 200, ar.text
    a = ar.json()
    rev = float(a.get("revenue_gross", 0))
    fee = float(a.get("platform_fee", 0))
    expected = round(rev * 0.03, 2)
    assert abs(fee - expected) < 0.02, f"fee {fee} != 3% of {rev} ({expected})"
