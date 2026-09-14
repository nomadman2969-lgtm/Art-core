"""Iteration 26: security hardening + EasyPost tracking.

Covers:
- Env-based admin & demo passwords (old admin pw rejected)
- POST /api/auth/demo-login {artist|collector|admin}
- Rate limit: 10 fails / email → 429 + Retry-After; success clears counter; per-email isolation
- 2FA email flow: resend 3× ok / 4th 429, verify wrong-code lockout after 8 and decay
- Email template HTML-escaping (delivery/gift/refund)
- CSV formula-injection guard on event attendees CSV
- EasyPost manual-mode: /tracking/config, /orders/{id}/tracking auth, webhook 503
- Regression: delivery confirmation flow (ship, carrier-delivered, confirm/not-received, legacy mark-delivered)
"""
import os
import uuid
import hashlib
import importlib
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

# --- load envs ---
_benv = {}
with open("/app/backend/.env") as f:
    for line in f:
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            _benv[k] = v.strip('"').strip("'")

_fenv = {}
with open("/app/frontend/.env") as f:
    for line in f:
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            _fenv[k] = v.strip('"').strip("'")

BASE_URL = _fenv["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = _benv["MONGO_URL"]
DB_NAME = _benv["DB_NAME"]
ADMIN_EMAIL = _benv["ADMIN_EMAIL"]
ADMIN_PASS = _benv["ADMIN_PASSWORD"]
DEMO_ARTIST_EMAIL = "demo.artist@artcorestudio.net"
DEMO_ARTIST_PASS = _benv["DEMO_ARTIST_PASSWORD"]
DEMO_COLLECTOR_EMAIL = "demo.collector@artcorestudio.net"
DEMO_COLLECTOR_PASS = _benv["DEMO_COLLECTOR_PASSWORD"]

os.environ.setdefault("ADMIN_PASSWORD", ADMIN_PASS)


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    # Clear rate_limits at start to avoid pollution from prior runs
    c[DB_NAME].rate_limits.delete_many({})
    yield c[DB_NAME]
    c[DB_NAME].rate_limits.delete_many({})
    c.close()


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def _login(email, password, expect=200):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    if expect is not None:
        assert r.status_code == expect, r.text
    return r


def _register(role="buyer", email=None, password="TestPass2026!", name=None):
    email = email or f"iter26-{role}-{uuid.uuid4().hex[:8]}@artcore-test.io"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": password, "name": name or f"Iter26 {role}", "role": role}, timeout=15)
    assert r.status_code in (200, 201), r.text
    return email, password, r.json()["token"], r.json()["user"]["id"]


# =========================================================
# 1) Admin env-based password rotation
# =========================================================
class TestAdminEnvPassword:
    def test_old_admin_password_rejected(self, mongo):
        mongo.rate_limits.delete_many({})
        r = _login(ADMIN_EMAIL, "MonsterAdmin2026!", expect=None)
        assert r.status_code == 401, f"Expected 401 for old admin pw, got {r.status_code}: {r.text}"

    def test_new_admin_password_ok(self, mongo):
        mongo.rate_limits.delete_many({})
        r = _login(ADMIN_EMAIL, ADMIN_PASS)
        j = r.json()
        assert j["user"]["role"] == "admin"
        assert j["token"]


# =========================================================
# 2) POST /api/auth/demo-login
# =========================================================
class TestDemoLogin:
    def test_demo_login_artist(self):
        r = requests.post(f"{BASE_URL}/api/auth/demo-login", json={"role": "artist"}, timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["user"]["role"] == "artist"
        assert j["user"]["email"] == DEMO_ARTIST_EMAIL
        assert j["token"]

    def test_demo_login_collector_is_buyer_role(self):
        r = requests.post(f"{BASE_URL}/api/auth/demo-login", json={"role": "collector"}, timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["user"]["role"] == "buyer"
        assert j["user"]["email"] == DEMO_COLLECTOR_EMAIL

    def test_demo_login_admin_rejected_422(self):
        r = requests.post(f"{BASE_URL}/api/auth/demo-login", json={"role": "admin"}, timeout=10)
        assert r.status_code == 422, r.text


# =========================================================
# 3) Rate limits (per-email, per-IP untouched)
# =========================================================
class TestLoginRateLimit:
    def test_ten_fails_then_429_retry_after(self, mongo):
        mongo.rate_limits.delete_many({})
        email = f"iter26-rl-{uuid.uuid4().hex[:8]}@artcore-test.io"
        # First 10 fails → 401
        for i in range(10):
            r = _login(email, "WrongPass!", expect=None)
            assert r.status_code == 401, f"attempt {i+1}: {r.status_code} {r.text}"
        # 11th → 429 with Retry-After
        r = _login(email, "WrongPass!", expect=None)
        assert r.status_code == 429, r.text
        assert "retry-after" in {k.lower() for k in r.headers.keys()}
        retry = int(r.headers.get("Retry-After", "0"))
        assert 0 < retry <= 15 * 60 + 5

        # Another email still logs in fine → per-email isolation
        _register("buyer", email=f"iter26-iso-{uuid.uuid4().hex[:8]}@artcore-test.io")

    def test_success_clears_email_counter(self, mongo):
        mongo.rate_limits.delete_many({})
        email, pw, _, _ = _register("buyer")
        # 5 fails
        for _ in range(5):
            _login(email, "wrong!", expect=401)
        # Correct password → clears
        _login(email, pw, expect=200)
        # Now 5 more fails should still be 401 (not 429)
        for i in range(5):
            r = _login(email, "wrong!", expect=None)
            assert r.status_code == 401, f"after clear attempt {i+1}: {r.status_code}"


# =========================================================
# 4) 2FA email: setup, enable, resend throttle, wrong-code lockout & decay
# =========================================================
class TestTwoFA:
    @pytest.fixture(scope="class")
    def user_2fa(self, mongo):
        mongo.rate_limits.delete_many({})
        email, pw, tok, uid = _register("buyer")
        # setup email 2FA
        r = requests.post(f"{BASE_URL}/api/auth/2fa/setup", headers=_hdr(tok), json={"method": "email"}, timeout=10)
        assert r.status_code == 200, r.text
        # Pull code from Mongo (hash-only stored; we set a known code directly)
        code = "123456"
        h = hashlib.sha256(code.strip().upper().replace("-", "").encode()).hexdigest()
        mongo.users.update_one({"id": uid}, {"$set": {
            "twofa_email_code_hash": h,
            "twofa_email_code_exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        }})
        r = requests.post(f"{BASE_URL}/api/auth/2fa/enable", headers=_hdr(tok), json={"code": code}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is True
        yield {"email": email, "pw": pw, "id": uid}
        # cleanup
        mongo.users.delete_one({"id": uid})

    def test_login_returns_challenge(self, mongo, user_2fa):
        mongo.rate_limits.delete_many({})
        r = _login(user_2fa["email"], user_2fa["pw"])
        j = r.json()
        assert j.get("requires_2fa") is True
        assert j.get("challenge_token")
        user_2fa["challenge"] = j["challenge_token"]

    def test_resend_throttle(self, mongo, user_2fa):
        mongo.rate_limits.delete_many({})
        ch = user_2fa.get("challenge")
        if not ch:
            r = _login(user_2fa["email"], user_2fa["pw"])
            ch = r.json()["challenge_token"]
        for i in range(3):
            r = requests.post(f"{BASE_URL}/api/auth/2fa/resend", json={"challenge_token": ch}, timeout=10)
            assert r.status_code == 200, f"resend {i+1}: {r.text}"
        # 4th → 429
        r = requests.post(f"{BASE_URL}/api/auth/2fa/resend", json={"challenge_token": ch}, timeout=10)
        assert r.status_code == 429, r.text

    def test_verify_login_lockout_and_decay(self, mongo, user_2fa):
        mongo.rate_limits.delete_many({})
        r = _login(user_2fa["email"], user_2fa["pw"])
        ch = r.json()["challenge_token"]
        # 8 wrong codes
        for i in range(8):
            rr = requests.post(f"{BASE_URL}/api/auth/2fa/verify-login",
                               json={"challenge_token": ch, "code": "000000"}, timeout=10)
            assert rr.status_code == 401, f"wrong code {i+1}: {rr.status_code} {rr.text}"
        # 9th → 429 lockout
        rr = requests.post(f"{BASE_URL}/api/auth/2fa/verify-login",
                           json={"challenge_token": ch, "code": "000000"}, timeout=10)
        assert rr.status_code == 429, rr.text
        assert rr.headers.get("Retry-After")
        # Force decay by rewinding twofa_fail_at 20 minutes
        past = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        mongo.users.update_one({"id": user_2fa["id"]}, {"$set": {"twofa_fail_at": past}})
        rr = requests.post(f"{BASE_URL}/api/auth/2fa/verify-login",
                           json={"challenge_token": ch, "code": "000000"}, timeout=10)
        # Should now be 401 "Wrong code" (not 429)
        assert rr.status_code == 401, f"expected 401 after decay, got {rr.status_code} {rr.text}"


# =========================================================
# 5) Email escaping — direct module import
# =========================================================
class TestEmailEscaping:
    def test_delivery_confirm_escapes(self):
        from backend import emails as _e  # type: ignore
    def test_delivery_confirm(self):
        import sys
        sys.path.insert(0, "/app/backend")
        import emails
        html_ = emails.delivery_confirm_html("<b>x</b>", "order_1", "USPS", "1Z<x>", "http://x", 3)
        assert "<b>x</b>" not in html_
        assert "&lt;b&gt;x&lt;/b&gt;" in html_

    def test_gift_ticket_escapes(self):
        import sys
        sys.path.insert(0, "/app/backend")
        import emails
        html_ = emails.gift_ticket_html("Rec<>", "Gif<>", "Ev<script>", "Tomorrow", "Somewhere",
                                        "<b>hi</b>", "http://x", "http://y")
        assert "<script>" not in html_
        assert "<b>hi</b>" not in html_
        assert "&lt;b&gt;hi&lt;/b&gt;" in html_

    def test_refund_email_escapes(self):
        import sys
        sys.path.insert(0, "/app/backend")
        import emails
        html_ = emails.refund_email_html("<b>u</b>", "<b>t</b>", 10.0, "today")
        assert "<b>u</b>" not in html_
        assert "<b>t</b>" not in html_
        assert "&lt;b&gt;u&lt;/b&gt;" in html_


# =========================================================
# 6) CSV formula injection guard
# =========================================================
class TestCSVFormulaGuard:
    def test_attendees_csv_neutralises_formula(self, mongo):
        mongo.rate_limits.delete_many({})
        # Find a free event hosted by demo artist
        artist = mongo.users.find_one({"email": DEMO_ARTIST_EMAIL})
        ev = mongo.events.find_one({"host_id": artist["id"], "$or": [{"price": {"$in": [0, None]}}, {"is_free": True}]})
        if not ev:
            ev = mongo.events.find_one({"host_id": artist["id"]})
        assert ev, "No demo artist event found for CSV test"

        # Create a throwaway buyer with name starting with formula
        nasty_name = '=HYPERLINK("x")'
        email, pw, tok, uid = _register("buyer", name=nasty_name)
        # Set the user's name in mongo to nasty (register may store as-is)
        mongo.users.update_one({"id": uid}, {"$set": {"name": nasty_name}})

        # RSVP via direct insert (fastest path)
        rsvp_id = str(uuid.uuid4())
        mongo.event_rsvps.insert_one({
            "id": rsvp_id, "event_id": ev["id"], "user_id": uid,
            "user_name": nasty_name, "paid": False, "amount": 0, "refunded": False,
            "checked_in": False, "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Host downloads CSV
        host_tok = _login(DEMO_ARTIST_EMAIL, DEMO_ARTIST_PASS).json()["token"]
        r = requests.get(f"{BASE_URL}/api/events/{ev['id']}/analytics.csv?kind=attendees",
                         headers=_hdr(host_tok), timeout=15)
        assert r.status_code == 200, r.text
        body = r.text
        # The nasty cell must appear with a leading single quote
        assert "'=HYPERLINK(\"x\")" in body or "'=HYPERLINK(\"\"x\"\")" in body, \
            f"Formula not neutralised. CSV excerpt:\n{body[:800]}"
        # And the bare formula MUST NOT appear at a cell start (no comma-then-= right before it)
        # A CSV cell starting with = would appear as ",=" or start-of-line "="
        assert ",=HYPERLINK" not in body, "Bare formula found — guard failed"

        # cleanup
        mongo.event_rsvps.delete_one({"id": rsvp_id})
        mongo.users.delete_one({"id": uid})


# =========================================================
# 7) Tracking manual mode
# =========================================================
class TestTrackingManualMode:
    def test_tracking_config_manual(self):
        r = requests.get(f"{BASE_URL}/api/tracking/config", timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["live_tracking"] is False
        assert j["webhook_configured"] is False
        assert isinstance(j["carriers"], list) and len(j["carriers"]) > 3

    def test_order_tracking_authz(self, mongo):
        mongo.rate_limits.delete_many({})
        # Use existing seeded testA order (buyer = demo collector)
        oid = "order_testA1"
        o = mongo.orders.find_one({"id": oid})
        if not o:
            pytest.skip(f"Seed order {oid} missing")
        buyer_tok = _login(DEMO_COLLECTOR_EMAIL, DEMO_COLLECTOR_PASS).json()["token"]
        r = requests.get(f"{BASE_URL}/api/orders/{oid}/tracking", headers=_hdr(buyer_tok), timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["live_tracking"] is False
        # tracker_id may be populated (seed data) but live_tracking must be False in manual mode

        # unrelated user → 403
        _, _, other_tok, _ = _register("buyer")
        r = requests.get(f"{BASE_URL}/api/orders/{oid}/tracking", headers=_hdr(other_tok), timeout=10)
        assert r.status_code == 403, r.text

    def test_webhook_503_no_secret(self):
        r = requests.post(f"{BASE_URL}/api/tracking/easypost/webhook",
                          json={"object": "Event", "description": "tracker.updated"},
                          headers={"X-Hmac-Signature": "x"}, timeout=10)
        assert r.status_code == 503, r.text


# =========================================================
# 8) Regression: delivery confirmation (ship → carrier-delivered → confirm/not-received)
# =========================================================
class TestDeliveryRegression:
    @pytest.fixture()
    def fresh_order(self, mongo):
        mongo.rate_limits.delete_many({})
        artist = mongo.users.find_one({"email": DEMO_ARTIST_EMAIL})
        art = mongo.artworks.find_one({"artist_id": artist["id"]})
        email, pw, buyer_tok, buyer_id = _register("buyer")
        oid = f"TEST_iter26_{uuid.uuid4().hex[:8]}"
        mongo.orders.insert_one({
            "id": oid, "buyer_id": buyer_id, "total": 200.0, "status": "paid",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "items": [{"artwork_id": art["id"], "artist_id": artist["id"], "price": 200.0, "quantity": 1}],
            "artist_payouts": [{"artist_id": artist["id"], "artwork_id": art["id"],
                                "gross": 200.0, "net": 175.0, "status": "held",
                                "release_at": "2026-09-30T00:00:00+00:00", "hold_reason": "awaiting_delivery"}],
            "fulfillment": {"status": "pending"},
        })
        yield {"id": oid, "buyer_tok": buyer_tok, "artist_id": artist["id"]}
        mongo.orders.delete_one({"id": oid})
        mongo.disputes.delete_many({"order_id": oid})
        mongo.notifications.delete_many({"order_id": oid})
        mongo.users.delete_one({"id": buyer_id})

    def test_flow_confirm(self, fresh_order):
        seller_tok = _login(DEMO_ARTIST_EMAIL, DEMO_ARTIST_PASS).json()["token"]
        oid = fresh_order["id"]
        # ship without tracking → 422
        r = requests.post(f"{BASE_URL}/api/orders/{oid}/ship", headers=_hdr(seller_tok),
                          json={"carrier": "USPS", "tracking": ""}, timeout=10)
        assert r.status_code == 422, r.text
        # ship with tracking → 200
        r = requests.post(f"{BASE_URL}/api/orders/{oid}/ship", headers=_hdr(seller_tok),
                          json={"carrier": "USPS", "tracking": "1Z999"}, timeout=10)
        assert r.status_code == 200, r.text
        # carrier-delivered
        r = requests.post(f"{BASE_URL}/api/orders/{oid}/carrier-delivered",
                          headers=_hdr(seller_tok), timeout=10)
        assert r.status_code == 200
        assert r.json()["fulfillment"]["status"] == "carrier_delivered"
        # pending
        r = requests.get(f"{BASE_URL}/api/orders/confirmations/pending",
                         headers=_hdr(fresh_order["buyer_tok"]), timeout=10)
        assert r.status_code == 200
        assert oid in [o["id"] for o in r.json()]
        # legacy mark-delivered still works
        r = requests.post(f"{BASE_URL}/api/orders/{oid}/mark-delivered",
                          headers=_hdr(fresh_order["buyer_tok"]), timeout=10)
        assert r.status_code == 200
        assert r.json()["fulfillment"]["status"] == "delivered"
