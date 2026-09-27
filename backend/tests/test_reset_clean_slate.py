"""Backend tests for /api/admin/reset-to-clean-slate + verify clean state."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@artcorestudio.net"
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _login(session, email, password):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    return r


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def test_settings_clean_state():
    r = requests.get(f"{BASE_URL}/api/settings")
    assert r.status_code == 200, r.text
    data = r.json()
    # Look for founding numbers in various possible shapes
    print("settings:", data)
    # Common shapes:
    taken = data.get("founding_taken")
    if taken is None and "founding" in data:
        taken = data["founding"].get("taken")
    assert taken == 0, f"Expected founding_taken=0, got {taken}. Full: {data}"


def test_admin_stats_zero(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/stats")
    assert r.status_code == 200, r.text
    data = r.json()
    print("admin stats:", data)
    # Zero fields
    for k in ("total_orders", "revenue", "artists", "buyers", "artworks_live"):
        if k in data:
            assert (data[k] == 0) or (data[k] == 0.0), f"{k} not zero: {data[k]}"


def test_admin_disputes_empty(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/disputes")
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", body.get("disputes", []))
    assert items == [] or len(items) == 0, f"Disputes not empty: {items}"


def test_admin_orders_empty(admin_session):
    # Try multiple candidate endpoints
    for path in ("/api/admin/orders", "/api/orders", "/api/admin/sales"):
        r = admin_session.get(f"{BASE_URL}{path}")
        if r.status_code == 200:
            body = r.json()
            items = body if isinstance(body, list) else body.get("items", body.get("orders", []))
            print(f"{path} -> {len(items)} items")
            assert len(items) == 0, f"{path} has items: {items}"
            return
    pytest.skip("No orders endpoint responded 200")


def test_artists_list_no_test_users():
    r = requests.get(f"{BASE_URL}/api/artists")
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", body.get("artists", []))
    print(f"artists count: {len(items)}")
    # 0 or 1 (admin only)
    assert len(items) <= 1, f"Too many artists: {len(items)}"


def test_reset_flow_full(admin_session):
    # 1. Register a throwaway artist
    email = f"tw_{int(time.time())}@example.com"
    password = "Throwaway123!"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "role": "artist", "name": "Throwaway Artist"},
    )
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    print("registered:", email)

    # 2. Confirm founding_taken becomes 1
    s = requests.get(f"{BASE_URL}/api/settings").json()
    taken = s.get("founding_taken") if "founding_taken" in s else (s.get("founding") or {}).get("taken")
    assert taken == 1, f"Expected founding_taken=1, got {taken}"

    # 3. Wrong phrase -> 400
    r = admin_session.post(
        f"{BASE_URL}/api/admin/reset-to-clean-slate", json={"confirm": "wrong phrase"}
    )
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"

    # 4. As non-admin -> 403
    tw = requests.Session()
    lr = _login(tw, email, password)
    assert lr.status_code == 200, f"throwaway login failed: {lr.text}"
    tw_token = lr.json().get("access_token") or lr.json().get("token")
    if tw_token:
        tw.headers.update({"Authorization": f"Bearer {tw_token}"})
    r = tw.post(f"{BASE_URL}/api/admin/reset-to-clean-slate", json={"confirm": "DELETE EVERYTHING"})
    assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"

    # 5. As admin with correct phrase -> 200 removed.users >= 1
    r = admin_session.post(
        f"{BASE_URL}/api/admin/reset-to-clean-slate", json={"confirm": "DELETE EVERYTHING"}
    )
    assert r.status_code == 200, f"reset failed: {r.status_code} {r.text}"
    body = r.json()
    print("reset body:", body)
    removed = body.get("removed", {})
    assert removed.get("users", 0) >= 1, f"users removed not >=1: {removed}"

    # 6. founding_taken back to 0
    s = requests.get(f"{BASE_URL}/api/settings").json()
    taken = s.get("founding_taken") if "founding_taken" in s else (s.get("founding") or {}).get("taken")
    assert taken == 0, f"founding_taken not 0 after reset: {taken}"

    # 7. Throwaway can no longer log in
    r = _login(requests.Session(), email, password)
    assert r.status_code == 401, f"throwaway should not login, got {r.status_code}"


def test_final_cleanup(admin_session):
    """Final safety reset to leave DB clean."""
    r = admin_session.post(
        f"{BASE_URL}/api/admin/reset-to-clean-slate", json={"confirm": "DELETE EVERYTHING"}
    )
    assert r.status_code == 200, r.text
    s = requests.get(f"{BASE_URL}/api/settings").json()
    taken = s.get("founding_taken") if "founding_taken" in s else (s.get("founding") or {}).get("taken")
    assert taken == 0
