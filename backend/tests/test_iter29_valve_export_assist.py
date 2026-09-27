"""Iter 29 — Dispute safety valve + admin export + Claude Listing Assistant."""
import io
import os
import json
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
import requests
from PIL import Image, ImageDraw
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://monster-curated.preview.emergentagent.com"
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "house_of_monster")
ADMIN_EMAIL = "admin@artcorestudio.net"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", os.environ["ADMIN_PASSWORD"])

_mongo = MongoClient(MONGO_URL)[DB_NAME]


# ---------- helpers ----------
def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _register(role="artist"):
    email = f"iter29_{role}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "TestPass123!"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": f"iter29 {role}", "role": role}, timeout=15)
    assert r.status_code in (200, 201), f"register: {r.status_code} {r.text[:200]}"
    return email, pw, r.json()["token"], r.json()["user"]["id"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token():
    # Clear rate limits for admin email up-front to avoid flakes
    _mongo.rate_limits.delete_many({})
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def artist():
    email, pw, token, uid = _register("artist")
    return {"email": email, "pw": pw, "token": token, "id": uid}


@pytest.fixture(scope="module")
def buyer():
    email, pw, token, uid = _register("buyer")
    return {"email": email, "pw": pw, "token": token, "id": uid}


def _make_real_jpeg() -> bytes:
    """Real-features JPEG (edges, colors, shapes)."""
    img = Image.new("RGB", (640, 480), (30, 40, 60))
    d = ImageDraw.Draw(img)
    for i in range(0, 640, 20):
        d.line([(i, 0), (i + 40, 480)], fill=(200 - i // 4, 100, 50 + i // 4), width=2)
    d.ellipse([100, 80, 320, 300], fill=(220, 90, 60), outline=(255, 255, 200), width=4)
    d.rectangle([360, 200, 560, 400], fill=(30, 160, 120), outline=(255, 255, 255), width=3)
    d.polygon([(200, 350), (280, 250), (360, 350), (280, 450)], fill=(255, 210, 40))
    for x in range(50, 620, 8):
        d.point((x, 30 + (x % 40)), fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


# ============================================================
# 1. DISPUTE SAFETY VALVE
# ============================================================
@pytest.fixture(scope="module")
def valve_seed(admin_token, artist, buyer):
    """Seed orders A, B, C + disputes."""
    now = datetime.now(timezone.utc)
    d8 = (now - timedelta(days=8)).isoformat()
    d5 = (now - timedelta(days=5)).isoformat()

    def _mk(order_id, dispute_id, created_at, reason, order_extra):
        _mongo.orders.delete_one({"id": order_id})
        _mongo.disputes.delete_one({"id": dispute_id})
        order = {
            "id": order_id,
            "buyer_id": buyer["id"],
            "session_id": None,
            "total": 100.0,
            "currency": "usd",
            "items": [{"artwork_id": f"art_{order_id}", "artist_id": artist["id"], "price": 100.0, "quantity": 1}],
            "artist_payouts": [{
                "artist_id": artist["id"], "artwork_id": f"art_{order_id}", "gross": 100.0,
                "processing_fee": 3.2, "net": 92.8, "status": "held",
                "release_at": None, "frozen_release_at": None, "hold_reason": "disputed",
            }],
            "fulfillment": {"status": "pending", "tracking": None, "carrier": None},
            "created_at": created_at,
            "dispute_status": "open",
            **order_extra,
        }
        dispute = {
            "id": dispute_id,
            "order_id": order_id,
            "buyer_id": buyer["id"],
            "seller_id": artist["id"],
            "reason": reason,
            "status": "open",
            "created_at": created_at,
            "updated_at": created_at,
            "history": [],
        }
        _mongo.orders.insert_one(order)
        _mongo.disputes.insert_one(dispute)

    # A: 8-days-old, not_received, carrier-confirmed delivery, has tracking → expect reject
    _mk("iter29_orderA", "iter29_dispA", d8, "not_received", {
        "session_id": "cs_fake_will_fail_but_not_used_in_reject",
        "fulfillment": {"status": "carrier_delivered", "carrier": "usps", "tracking": "9400111899223197428347",
                        "carrier_delivered_source": "carrier:webhook", "delivered_at": (now - timedelta(days=9)).isoformat()},
    })
    # B: 8-days-old, damaged, NO session_id → refund_full path will fail
    _mk("iter29_orderB", "iter29_dispB", d8, "damaged", {
        "session_id": None,
        "fulfillment": {"status": "delivered", "tracking": None, "carrier": None},
    })
    # C: 5-days-old, not_received → warn only
    _mk("iter29_orderC", "iter29_dispC", d5, "not_received", {
        "session_id": None,
        "fulfillment": {"status": "pending", "tracking": None, "carrier": None},
    })
    # Clean any prior admin notifications for these dispute ids
    _mongo.notifications.delete_many({"dispute_id": {"$in": ["iter29_dispA", "iter29_dispB", "iter29_dispC"]}})
    yield
    # cleanup
    _mongo.orders.delete_many({"id": {"$in": ["iter29_orderA", "iter29_orderB", "iter29_orderC"]}})
    _mongo.disputes.delete_many({"id": {"$in": ["iter29_dispA", "iter29_dispB", "iter29_dispC"]}})
    _mongo.notifications.delete_many({"dispute_id": {"$in": ["iter29_dispA", "iter29_dispB", "iter29_dispC"]}})


def test_sweep_forbidden_non_admin(valve_seed, artist):
    r = requests.post(f"{API}/admin/disputes/sweep", headers=_headers(artist["token"]), timeout=30)
    assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"


def test_sweep_resolves_A_warns_C_fails_B(valve_seed, admin_token):
    r = requests.post(f"{API}/admin/disputes/sweep", headers=_headers(admin_token), timeout=60)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "warned" in body and "resolved" in body

    # A → rejected
    dA = _mongo.disputes.find_one({"id": "iter29_dispA"})
    assert dA["status"] == "rejected", f"A status: {dA.get('status')} err={dA.get('auto_resolve_error')}"
    assert dA.get("resolution") == "reject"
    assert dA.get("auto_resolved") is True
    oA = _mongo.orders.find_one({"id": "iter29_orderA"})
    assert (oA.get("fulfillment") or {}).get("status") == "delivered"
    assert oA["artist_payouts"][0].get("release_at"), "payout release_at should be set (unfrozen)"
    assert oA["artist_payouts"][0].get("hold_reason") == "dispute_rejected"

    # B → still open, auto_resolve_error set, admin got dispute_auto_failed
    dB = _mongo.disputes.find_one({"id": "iter29_dispB"})
    assert dB["status"] == "open", f"B unexpected status {dB['status']}"
    assert dB.get("auto_resolve_error"), "B should have auto_resolve_error"
    failed_notifs = list(_mongo.notifications.find({"kind": "dispute_auto_failed", "dispute_id": "iter29_dispB"}))
    assert len(failed_notifs) >= 1, "expected at least one dispute_auto_failed admin notification"

    # C → warned, not resolved
    dC = _mongo.disputes.find_one({"id": "iter29_dispC"})
    assert dC["status"] == "open"
    assert dC.get("auto_warned") is True
    warn_notifs = list(_mongo.notifications.find({"kind": "dispute_auto_warning", "dispute_id": "iter29_dispC"}))
    assert len(warn_notifs) >= 1


def test_sweep_idempotent(valve_seed, admin_token):
    warn_before = _mongo.notifications.count_documents({"kind": "dispute_auto_warning", "dispute_id": "iter29_dispC"})
    fail_before = _mongo.notifications.count_documents({"kind": "dispute_auto_failed", "dispute_id": "iter29_dispB"})
    r = requests.post(f"{API}/admin/disputes/sweep", headers=_headers(admin_token), timeout=60)
    assert r.status_code == 200
    warn_after = _mongo.notifications.count_documents({"kind": "dispute_auto_warning", "dispute_id": "iter29_dispC"})
    fail_after = _mongo.notifications.count_documents({"kind": "dispute_auto_failed", "dispute_id": "iter29_dispB"})
    assert warn_after == warn_before, f"C re-warned: {warn_before} -> {warn_after}"
    assert fail_after == fail_before, f"B re-notified: {fail_before} -> {fail_after}"


# ============================================================
# 2. SETTINGS: dispute_auto_days
# ============================================================
def test_settings_patch_valid(admin_token):
    r = requests.patch(f"{API}/admin/settings", json={"dispute_auto_days": 10}, headers=_headers(admin_token), timeout=15)
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("dispute_auto_days") == 10
    pub = requests.get(f"{API}/settings", timeout=15)
    assert pub.status_code == 200
    assert pub.json().get("dispute_auto_days") == 10


def test_settings_patch_invalid_low(admin_token):
    r = requests.patch(f"{API}/admin/settings", json={"dispute_auto_days": 1}, headers=_headers(admin_token), timeout=15)
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:200]}"


def test_settings_restore(admin_token):
    r = requests.patch(f"{API}/admin/settings", json={"dispute_auto_days": 7}, headers=_headers(admin_token), timeout=15)
    assert r.status_code == 200
    assert r.json().get("dispute_auto_days") == 7


# ============================================================
# 3. EXPORT
# ============================================================
def test_export_admin_zip(admin_token):
    r = requests.get(f"{API}/admin/export.zip", headers=_headers(admin_token), timeout=60)
    assert r.status_code == 200, r.text[:200]
    assert r.headers.get("content-type", "").startswith("application/zip")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    expected = {"artcore_export.json", "users.csv", "orders.csv", "payouts.csv", "transactions.csv", "README.txt"}
    assert expected.issubset(names), f"missing files, got: {names}"
    dump = json.loads(z.read("artcore_export.json"))
    assert isinstance(dump.get("users"), list) and len(dump["users"]) >= 1
    for u in dump["users"]:
        for f in ("password_hash", "twofa_secret", "recovery_codes", "trusted_devices"):
            assert f not in u, f"user has sensitive field {f}"
    users_csv = z.read("users.csv").decode()
    header = users_csv.splitlines()[0]
    for col in ("id", "email", "name", "role"):
        assert col in header, f"users.csv missing column {col}"


def test_export_artist_forbidden(artist):
    r = requests.get(f"{API}/admin/export.zip", headers=_headers(artist["token"]), timeout=30)
    assert r.status_code == 403


def test_export_anon_unauthenticated():
    r = requests.get(f"{API}/admin/export.zip", timeout=30)
    assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ============================================================
# 4. LISTING ASSIST
# ============================================================
@pytest.fixture(scope="module")
def uploaded_image(artist):
    files = {"file": (f"iter29_{uuid.uuid4().hex[:6]}.jpg", _make_real_jpeg(), "image/jpeg")}
    r = requests.post(f"{API}/upload/image", headers=_headers(artist["token"]), files=files, timeout=30)
    assert r.status_code == 200, f"upload failed {r.status_code} {r.text[:200]}"
    body = r.json()
    # storage_path or path — accept either shape
    path = body.get("storage_path") or body.get("path") or body.get("url") or ""
    assert path, f"upload returned no path: {body}"
    return path


def test_assist_missing_image_path(artist):
    r = requests.post(f"{API}/studio/listing-assist", json={"section": "art"}, headers=_headers(artist["token"]), timeout=15)
    assert r.status_code == 422


def test_assist_bogus_path_404(artist):
    r = requests.post(f"{API}/studio/listing-assist",
                      json={"image_path": "does/not/exist.jpg", "section": "art"},
                      headers=_headers(artist["token"]), timeout=15)
    assert r.status_code == 404


def test_assist_buyer_forbidden(buyer, uploaded_image):
    r = requests.post(f"{API}/studio/listing-assist",
                      json={"image_path": uploaded_image, "section": "art"},
                      headers=_headers(buyer["token"]), timeout=15)
    assert r.status_code == 403


def test_assist_other_users_upload_404(uploaded_image, buyer):
    # register another artist and try to use first artist's image
    _, _, tok, _ = _register("artist")
    r = requests.post(f"{API}/studio/listing-assist",
                      json={"image_path": uploaded_image, "section": "art"},
                      headers=_headers(tok), timeout=15)
    assert r.status_code == 404


def test_assist_success(artist, uploaded_image):
    MEDIUMS = ["Oil", "Acrylic", "Watercolor", "Mixed Media", "Digital", "Photography", "Sculpture", "Print"]
    r = requests.post(f"{API}/studio/listing-assist",
                      json={"image_path": uploaded_image, "section": "art",
                            "hints": "Layered acrylic with warm palette, painted on canvas",
                            "width_in": 24, "height_in": 18},
                      headers=_headers(artist["token"]), timeout=90)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    for k in ("title", "description", "medium", "style", "color", "tags",
              "price_low", "price_high", "price_suggested", "price_note"):
        assert k in d, f"missing key {k}"
    assert d["medium"] in MEDIUMS
    assert 5 <= len(d["tags"]) <= 8
    assert d["price_low"] <= d["price_suggested"] <= d["price_high"]
    assert d["title"] and d["description"]
