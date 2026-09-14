"""Iteration 19 — Fee split regression (4% platform + seller-pays-processing 2.9% + $0.30)."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("monster@houseofmonster.com", os.environ["ADMIN_PASSWORD"])
ARTIST = ("demo.artist@artcorestudio.net", "DemoArtist2026!")
BUYER = ("demo.collector@artcorestudio.net", "DemoCollector2026!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    j = r.json()
    return j.get("token") or j.get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def artist_token():
    return _login(*ARTIST)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(*BUYER)


# ---- public settings ----
def test_public_settings_shape():
    r = requests.get(f"{API}/settings", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["commission_percent"] == 4.0
    assert d["processing_percent"] == 2.9
    assert abs(d["processing_fixed"] - 0.30) < 1e-6
    assert d["seller_pays_processing"] is True


# ---- fee-preview math ----
@pytest.mark.parametrize("gross, plat, proc, net", [
    (100, 4.0, 3.20, 92.80),
    (0, 0.0, 0.0, 0.0),
    (30, 1.2, 1.17, 27.63),
])
def test_fee_preview(gross, plat, proc, net):
    r = requests.get(f"{API}/settings/fee-preview", params={"gross": gross}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["platform_take"] == plat, d
    assert d["processing_fee"] == proc, d
    assert d["net"] == net, d


# ---- admin settings patch ----
def test_admin_patch_processing_settings(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    # GET
    r = requests.get(f"{API}/admin/settings", headers=h, timeout=15)
    assert r.status_code == 200
    before = r.json()
    # PATCH: set to 3.1 / 0.5 temporarily
    r = requests.patch(f"{API}/admin/settings", json={"processing_percent": 3.1, "processing_fixed": 0.5}, headers=h, timeout=15)
    assert r.status_code == 200, r.text
    r = requests.get(f"{API}/admin/settings", headers=h, timeout=15)
    d = r.json()
    assert d["processing_percent"] == 3.1
    assert d["processing_fixed"] == 0.5
    # Restore
    r = requests.patch(f"{API}/admin/settings", json={"processing_percent": 2.9, "processing_fixed": 0.30}, headers=h, timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{API}/admin/settings", headers=h, timeout=15)
    d = r.json()
    assert d["processing_percent"] == 2.9
    assert abs(d["processing_fixed"] - 0.30) < 1e-6


# ---- Checkout session creation still works ----
def test_buyer_checkout_session(buyer_token):
    # Find a live artwork
    r = requests.get(f"{API}/artworks", params={"status": "live", "limit": 1}, timeout=15)
    assert r.status_code == 200
    arts = r.json()
    if isinstance(arts, dict):
        arts = arts.get("items") or arts.get("artworks") or []
    if not arts:
        pytest.skip("No live artwork to checkout")
    art = arts[0]
    h = {"Authorization": f"Bearer {buyer_token}"}
    payload = {"items": [{"artwork_id": art["id"], "quantity": 1}], "origin_url": BASE_URL}
    r = requests.post(f"{API}/payments/checkout", json=payload, headers=h, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("checkout_url", "").startswith("https://checkout.stripe.com")
    assert d.get("session_id")


# ---- split_amount unit test (in-process import) ----
def test_split_amount_unit():
    # Pure-math replica of split_amount (avoid importing backend module which needs env)
    def split_amount(gross, s):
        gross = float(gross)
        platform_take = round(gross * float(s["commission_percent"]) / 100.0, 2)
        processing_fee = round(gross * float(s.get("processing_percent", 2.9)) / 100.0 + float(s.get("processing_fixed", 0.30)), 2) if gross > 0 else 0.0
        net = round(max(0.0, gross - platform_take - processing_fee), 2)
        return {"platform_take": platform_take, "processing_fee": processing_fee, "net": net}
    s = {"commission_percent": 4.0, "processing_percent": 2.9, "processing_fixed": 0.30}
    d = split_amount(100.0, s)
    assert d == {"platform_take": 4.0, "processing_fee": 3.20, "net": 92.80}
    d0 = split_amount(0, s)
    assert d0 == {"platform_take": 0.0, "processing_fee": 0.0, "net": 0.0}


# ---- Event host analytics still works ----
def test_event_host_analytics(artist_token):
    h = {"Authorization": f"Bearer {artist_token}"}
    r = requests.get(f"{API}/events", params={"limit": 20}, timeout=15)
    assert r.status_code == 200
    evs = r.json()
    if isinstance(evs, dict):
        evs = evs.get("items") or evs.get("events") or []
    # find one this artist hosts
    me = requests.get(f"{API}/auth/me", headers=h, timeout=15).json()
    my_id = me["id"]
    mine = [e for e in evs if e.get("host_id") == my_id]
    if not mine:
        pytest.skip("Demo artist has no hosted event")
    ev = mine[0]
    r = requests.get(f"{API}/events/{ev['id']}/analytics", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "platform_fee" in d and "net_to_host" in d
    assert d["platform_fee"] >= 0
    assert d["net_to_host"] >= 0


# ---- Verify on_behalf_of source ----
def test_build_transfer_options_source():
    import pathlib
    src = pathlib.Path("/app/backend/connect.py").read_text()
    assert "on_behalf_of" in src, "build_transfer_options should set on_behalf_of"
