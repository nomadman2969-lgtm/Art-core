"""Iteration 31: avatar upload/remove + 12% commission fee-preview + founding waiver."""
import os, io, base64, random, string
import pytest, requests
from PIL import Image

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@artcorestudio.net"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "atg-6+XxIRZe1zLUDCcwB!_a")


def _rand(n=6):
    return "".join(random.choices(string.ascii_lowercase, k=n))


def _feature_jpeg_bytes():
    im = Image.new("RGB", (200, 200), (20, 20, 20))
    px = im.load()
    for x in range(200):
        for y in range(200):
            px[x, y] = ((x * 3) % 255, (y * 5) % 255, ((x + y) * 2) % 255)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def artist():
    email = f"tw31_{_rand()}@example.com"
    r = requests.post(f"{BASE}/api/auth/register",
                      json={"email": email, "password": "PassPass1!", "name": "Iter31 Artist", "role": "artist"})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"email": email, "token": data["token"], "id": data["user"]["id"]}


# ---------------- Public /api/settings ----------------
def test_settings_commission_12():
    r = requests.get(f"{BASE}/api/settings")
    assert r.status_code == 200
    s = r.json()
    assert s["commission_percent"] == 12.0
    assert s["founding_rate"] == 4.0
    assert s["waiver_days"] == 30
    assert s["waiver_max_sales"] == 5


def test_fee_preview_gross_100_public():
    r = requests.get(f"{BASE}/api/settings/fee-preview?gross=100")
    assert r.status_code == 200
    d = r.json()
    assert d["platform_take"] == 12.0
    assert d["processing_fee"] == 3.2
    assert d["net"] == 84.8
    assert d["commission_percent"] == 12.0


# ---------------- Founding + waiver on new artist ----------------
def test_new_artist_is_founding_and_waived(artist):
    h = {"Authorization": f"Bearer {artist['token']}"}
    wm = requests.get(f"{BASE}/api/waiver/me", headers=h).json()
    assert wm["founding_member"] is True
    assert wm["locked_commission_percent"] == 4.0
    assert wm["standard_commission_percent"] == 12.0
    assert wm["active"] is True
    assert wm["effective_commission_percent"] == 0.0

    fp = requests.get(f"{BASE}/api/settings/fee-preview?gross=100", headers=h).json()
    assert fp["commission_percent"] == 0.0
    assert fp["fee_waived"] is True
    assert fp["founding_locked"] is True
    assert fp["platform_take"] == 0.0
    assert fp["net"] == 96.8


# ---------------- Avatar PATCH set + clear ----------------
def test_patch_me_avatar_set_and_clear(artist):
    h = {"Authorization": f"Bearer {artist['token']}"}
    p = requests.patch(f"{BASE}/api/auth/me", json={"avatar": "/uploads/x-test.jpg"}, headers=h)
    assert p.status_code == 200
    assert p.json()["avatar"] == "/uploads/x-test.jpg"
    me = requests.get(f"{BASE}/api/auth/me", headers=h).json()
    assert me["avatar"] == "/uploads/x-test.jpg"

    p2 = requests.patch(f"{BASE}/api/auth/me", json={"avatar": None}, headers=h)
    assert p2.status_code == 200
    assert p2.json().get("avatar") in (None, "")
    me2 = requests.get(f"{BASE}/api/auth/me", headers=h).json()
    assert me2.get("avatar") in (None, "")


# ---------------- Upload image + set avatar + public studio ----------------
def test_upload_image_and_set_avatar_visible_on_public_studio(artist):
    h = {"Authorization": f"Bearer {artist['token']}"}
    img = _feature_jpeg_bytes()
    files = {"file": ("avatar.jpg", img, "image/jpeg")}
    u = requests.post(f"{BASE}/api/upload/image", files=files, headers=h)
    assert u.status_code == 200, u.text
    path = u.json()["path"]
    assert path

    p = requests.patch(f"{BASE}/api/auth/me", json={"avatar": path}, headers=h)
    assert p.status_code == 200
    assert p.json()["avatar"] == path

    # public studio
    ap = requests.get(f"{BASE}/api/artists/{artist['id']}")
    assert ap.status_code == 200
    assert ap.json().get("avatar") == path

    # img URL loads (via /api/files/ endpoint)
    img_url = f"{BASE}/api/files/{path.lstrip('/')}"
    r = requests.get(img_url)
    assert r.status_code == 200, f"{img_url} -> {r.status_code}"
    assert "image" in r.headers.get("Content-Type", "")

    # clear
    requests.patch(f"{BASE}/api/auth/me", json={"avatar": None}, headers=h)
    ap2 = requests.get(f"{BASE}/api/artists/{artist['id']}").json()
    assert ap2.get("avatar") in (None, "")


# ---------------- Cleanup (reset to clean slate) ----------------
def test_zzz_cleanup_reset(admin_token):
    r = requests.post(f"{BASE}/api/admin/reset-to-clean-slate",
                      json={"confirm": "DELETE EVERYTHING"},
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    s = requests.get(f"{BASE}/api/settings").json()
    assert s["founding_taken"] == 0
