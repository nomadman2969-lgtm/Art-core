"""Backend tests for anti-chargeback delivery-confirmation flow.

Covers:
- ship (requires tracking)
- carrier-delivered (seller only; requires shipped)
- pending confirmations list (buyer)
- confirm-received → delivered + release_at ~2d, hold_reason delivered
- not-received → payout frozen (release_at null), dispute auto-opened w/ tracking_proof
- admin reject dispute → delivered + release_at restored, hold_reason dispute_rejected
- legacy mark-delivered still works
- notifications: order_delivered_confirm / order_received_confirmed / order_not_received
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if False else "https://monster-curated.preview.emergentagent.com"
# Load from frontend .env via file rather than env var
_env = {}
try:
    with open("/app/frontend/.env") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                _env[k] = v
    BASE_URL = _env.get("REACT_APP_BACKEND_URL", BASE_URL).rstrip("/")
except Exception:
    pass

# Backend Mongo
_benv = {}
with open("/app/backend/.env") as f:
    for line in f:
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            _benv[k] = v.strip('"').strip("'")
MONGO_URL = _benv["MONGO_URL"]
DB_NAME = _benv["DB_NAME"]

ADMIN_EMAIL = "monster@houseofmonster.com"
ADMIN_PASS = "MonsterAdmin2026!"
DEMO_ARTIST_EMAIL = "demo.artist@artcorestudio.net"
DEMO_ARTIST_PASS = "DemoArtist2026!"


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _register(role):
    email = f"test-{role}-{uuid.uuid4().hex[:8]}@artcore-test.io"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": "TestPass2026!", "name": f"Test {role}", "role": role}, timeout=15)
    assert r.status_code in (200, 201), r.text
    return email, "TestPass2026!", r.json().get("token") or _login(email, "TestPass2026!")


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def artist_ids(mongo):
    a = mongo.users.find_one({"email": DEMO_ARTIST_EMAIL})
    art = mongo.artworks.find_one({"artist_id": a["id"]})
    return a["id"], art["id"], _login(DEMO_ARTIST_EMAIL, DEMO_ARTIST_PASS)


@pytest.fixture()
def order(mongo, artist_ids):
    """Create a fresh buyer and an order in 'paid' state via direct Mongo insert."""
    artist_id, artwork_id, _ = artist_ids
    buyer_email, _, buyer_tok = _register("buyer")
    buyer = mongo.users.find_one({"email": buyer_email})
    oid = f"TEST_order_{uuid.uuid4().hex[:8]}"
    mongo.orders.insert_one({
        "id": oid,
        "buyer_id": buyer["id"],
        "total": 250.0,
        "status": "paid",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": [{"artwork_id": artwork_id, "artist_id": artist_id, "price": 250.0, "quantity": 1}],
        "artist_payouts": [{
            "artist_id": artist_id, "artwork_id": artwork_id, "gross": 250.0, "net": 220.0,
            "status": "held", "release_at": "2026-09-30T00:00:00+00:00", "hold_reason": "awaiting_delivery",
        }],
        "fulfillment": {"status": "pending"},
    })
    yield {"id": oid, "buyer_tok": buyer_tok, "buyer_id": buyer["id"], "artist_id": artist_id}
    # cleanup
    mongo.orders.delete_one({"id": oid})
    mongo.disputes.delete_many({"order_id": oid})
    mongo.notifications.delete_many({"order_id": oid})


# ---------- ship ----------
def test_ship_requires_tracking(order, artist_ids):
    _, _, seller_tok = artist_ids
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                      headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": ""}, timeout=10)
    assert r.status_code == 422, r.text


def test_ship_succeeds(order, artist_ids):
    _, _, seller_tok = artist_ids
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                      headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["fulfillment"]["status"] == "shipped"
    assert r.json()["fulfillment"]["tracking"] == "1Z999"


# ---------- carrier-delivered ----------
def test_carrier_delivered_400_when_not_shipped(order, artist_ids):
    _, _, seller_tok = artist_ids
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/carrier-delivered",
                      headers=_hdr(seller_tok), timeout=10)
    assert r.status_code == 400


def test_carrier_delivered_403_for_buyer(order, artist_ids):
    _, _, seller_tok = artist_ids
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                  headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/carrier-delivered",
                     headers=_hdr(order["buyer_tok"]), timeout=10)
    assert r.status_code == 403


def test_carrier_delivered_ok(order, artist_ids, mongo):
    _, _, seller_tok = artist_ids
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                  headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/carrier-delivered",
                      headers=_hdr(seller_tok), timeout=10)
    assert r.status_code == 200
    f = r.json()["fulfillment"]
    assert f["status"] == "carrier_delivered"
    assert f["carrier_delivered_source"] == "seller"
    # deadline ~3 days away
    deadline = datetime.fromisoformat(f["confirm_deadline"])
    delta = deadline - datetime.now(timezone.utc)
    assert 2.5 * 86400 < delta.total_seconds() < 3.5 * 86400
    # buyer notification
    n = mongo.notifications.find_one({"user_id": order["buyer_id"], "kind": "order_delivered_confirm", "order_id": order["id"]})
    assert n is not None


# ---------- pending confirmations ----------
def test_pending_confirmations_lists(order, artist_ids):
    _, _, seller_tok = artist_ids
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                  headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/carrier-delivered",
                  headers=_hdr(seller_tok), timeout=10)
    r = requests.get(f"{BASE_URL}/api/orders/confirmations/pending",
                     headers=_hdr(order["buyer_tok"]), timeout=10)
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert order["id"] in ids
    row = next(o for o in r.json() if o["id"] == order["id"])
    assert row["items"] and row["fulfillment"]["status"] == "carrier_delivered"


def test_pending_empty_for_new_buyer():
    _, _, buyer_tok = _register("buyer")
    r = requests.get(f"{BASE_URL}/api/orders/confirmations/pending",
                     headers=_hdr(buyer_tok), timeout=10)
    assert r.status_code == 200
    assert r.json() == []


# ---------- confirm received ----------
def test_confirm_received_and_second_call_400(order, artist_ids, mongo):
    _, _, seller_tok = artist_ids
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                  headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/carrier-delivered",
                  headers=_hdr(seller_tok), timeout=10)
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/confirm-received",
                     headers=_hdr(order["buyer_tok"]), timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["fulfillment"]["status"] == "delivered"
    p = j["artist_payouts"][0]
    assert p["hold_reason"] == "delivered"
    ra = datetime.fromisoformat(p["release_at"])
    delta = (ra - datetime.now(timezone.utc)).total_seconds()
    assert 1.5 * 86400 < delta < 2.5 * 86400
    # second call
    r2 = requests.post(f"{BASE_URL}/api/orders/{order['id']}/confirm-received",
                       headers=_hdr(order["buyer_tok"]), timeout=10)
    assert r2.status_code == 400
    # seller notification
    n = mongo.notifications.find_one({"user_id": order["artist_id"], "kind": "order_received_confirmed", "order_id": order["id"]})
    assert n is not None


def test_confirm_received_403_non_buyer(order, artist_ids):
    _, _, seller_tok = artist_ids
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                  headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/confirm-received",
                     headers=_hdr(seller_tok), timeout=10)
    assert r.status_code == 403


# ---------- not received + dispute ----------
def test_not_received_opens_dispute_and_freezes_payout(order, artist_ids, mongo):
    _, _, seller_tok = artist_ids
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                  headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/carrier-delivered",
                  headers=_hdr(seller_tok), timeout=10)
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/not-received",
                     headers=_hdr(order["buyer_tok"]), timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["fulfillment"]["status"] == "not_received"
    p = j["artist_payouts"][0]
    assert p["release_at"] is None
    assert p["hold_reason"] == "not_received"
    # dispute
    d = requests.get(f"{BASE_URL}/api/orders/{order['id']}/dispute",
                     headers=_hdr(order["buyer_tok"]), timeout=10).json()
    assert d and d["reason"] == "not_received"
    assert d["auto_opened"] is True
    assert d["tracking_proof"]["tracking"] == "1Z999"
    # second call
    r2 = requests.post(f"{BASE_URL}/api/orders/{order['id']}/not-received",
                       headers=_hdr(order["buyer_tok"]), timeout=10)
    assert r2.status_code == 400
    # seller notif
    assert mongo.notifications.find_one({"user_id": order["artist_id"], "kind": "order_not_received", "order_id": order["id"]}) is not None


# ---------- admin resolve reject ----------
def test_admin_reject_dispute_unfreezes(order, artist_ids, mongo):
    _, _, seller_tok = artist_ids
    admin_tok = _login(ADMIN_EMAIL, ADMIN_PASS)
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                  headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/carrier-delivered",
                  headers=_hdr(seller_tok), timeout=10)
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/not-received",
                  headers=_hdr(order["buyer_tok"]), timeout=10)
    d = requests.get(f"{BASE_URL}/api/orders/{order['id']}/dispute",
                     headers=_hdr(order["buyer_tok"]), timeout=10).json()
    r = requests.post(f"{BASE_URL}/api/admin/disputes/{d['id']}/resolve",
                      headers=_hdr(admin_tok), json={"action": "reject"}, timeout=15)
    assert r.status_code == 200, r.text
    o = mongo.orders.find_one({"id": order["id"]})
    assert o["fulfillment"]["status"] == "delivered"
    p = o["artist_payouts"][0]
    assert p["release_at"] is not None
    assert p["hold_reason"] == "dispute_rejected"
    ra = datetime.fromisoformat(p["release_at"])
    delta = (ra - datetime.now(timezone.utc)).total_seconds()
    assert 1.5 * 86400 < delta < 2.5 * 86400


# ---------- legacy mark-delivered ----------
def test_legacy_mark_delivered_from_shipped(order, artist_ids):
    _, _, seller_tok = artist_ids
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                  headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/mark-delivered",
                     headers=_hdr(order["buyer_tok"]), timeout=10)
    assert r.status_code == 200
    assert r.json()["fulfillment"]["status"] == "delivered"


def test_legacy_mark_delivered_from_carrier_delivered(order, artist_ids):
    _, _, seller_tok = artist_ids
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/ship",
                  headers=_hdr(seller_tok), json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
    requests.post(f"{BASE_URL}/api/orders/{order['id']}/carrier-delivered",
                  headers=_hdr(seller_tok), timeout=10)
    r = requests.post(f"{BASE_URL}/api/orders/{order['id']}/mark-delivered",
                     headers=_hdr(order["buyer_tok"]), timeout=10)
    assert r.status_code == 200
    assert r.json()["fulfillment"]["status"] == "delivered"
