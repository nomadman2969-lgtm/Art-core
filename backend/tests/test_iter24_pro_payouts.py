"""Iteration 24: Art Core Pro subscription + Depop-style payouts."""
import os
import sys
import time
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback: read frontend/.env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL"):
                BASE = ln.split("=", 1)[1].strip().strip('"').rstrip("/")

API = f"{BASE}/api"
ARTIST = ("demo.artist@artcorestudio.net", "DemoArtist2026!")
BUYER = ("demo.collector@artcorestudio.net", "DemoCollector2026!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} → {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def artist_token():
    return _login(*ARTIST)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(*BUYER)


from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

# Single persistent loop for the whole test module — motor binds to first loop it sees.
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


class _Runner:
    def run_until_complete(self, coro):
        return _LOOP.run_until_complete(coro)


@pytest.fixture(scope="module")
def event_loop():
    return _Runner()


@pytest.fixture(scope="module")
def db_conn():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=_LOOP)
    return client[os.environ["DB_NAME"]]


# ---------------- PRO backend ----------------
class TestProBackend:
    def test_plans_unauth(self):
        r = requests.get(f"{API}/pro/plans", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert len(data["perks"]) == 4
        assert data["prices"]["month"]["amount"] == 12
        assert data["prices"]["year"]["amount"] == 99
        assert data["founder_discount"] is False
        assert data["prices"]["month"]["founder_amount"] is None

    def test_plans_founder_artist(self, artist_token):
        r = requests.get(f"{API}/pro/plans", headers=_hdr(artist_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["founder_discount"] is True
        assert data["prices"]["month"]["founder_amount"] == 6
        assert data["prices"]["year"]["founder_amount"] == 49.5

    def test_checkout_buyer_400(self, buyer_token):
        r = requests.post(f"{API}/pro/checkout", headers=_hdr(buyer_token),
                          json={"interval": "month", "origin_url": "https://example.com"}, timeout=30)
        assert r.status_code == 400
        assert "artist" in r.text.lower()

    def test_status_demo_artist_inactive(self, artist_token):
        r = requests.get(f"{API}/pro/status", headers=_hdr(artist_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["active"] is False

    def test_checkout_artist_creates_session(self, artist_token, event_loop, db_conn):
        r = requests.post(f"{API}/pro/checkout", headers=_hdr(artist_token),
                          json={"interval": "month", "origin_url": "https://example.com"}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "stripe.com" in data["checkout_url"]
        sid = data["session_id"]
        # verify payment_transactions doc
        tx = event_loop.run_until_complete(db_conn.payment_transactions.find_one({"session_id": sid}))
        assert tx is not None
        assert tx["kind"] == "pro_subscription"


class TestProActivationSimulated:
    """Create throwaway artist, simulate active subscription via Mongo, verify status + auth/me."""

    @pytest.fixture(scope="class")
    def throwaway(self, event_loop, db_conn):
        email = f"throw_{uuid.uuid4().hex[:8]}@throwaway.artcorestudio.net"
        pw = "TestPass2026!"
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": pw, "name": "Throw Artist", "role": "artist"}, timeout=30)
        assert r.status_code in (200, 201), r.text
        tok = r.json().get("token") or _login(email, pw)
        user = event_loop.run_until_complete(db_conn.users.find_one({"email": email}))
        yield {"email": email, "token": tok, "id": user["id"]}
        # cleanup
        event_loop.run_until_complete(db_conn.users.delete_one({"id": user["id"]}))
        event_loop.run_until_complete(db_conn.artworks.delete_many({"artist_id": user["id"]}))
        event_loop.run_until_complete(db_conn.studio_configs.delete_many({"artist_id": user["id"]}))

    def test_activate_and_status(self, throwaway, event_loop, db_conn):
        end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        event_loop.run_until_complete(db_conn.users.update_one(
            {"id": throwaway["id"]},
            {"$set": {"pro": {"status": "active", "subscription_id": "sub_test",
                              "interval": "month", "amount": 6,
                              "current_period_end": end, "cancel_at_period_end": False}}}))
        r = requests.get(f"{API}/pro/status", headers=_hdr(throwaway["token"]), timeout=30)
        assert r.status_code == 200
        assert r.json()["active"] is True

        me = requests.get(f"{API}/auth/me", headers=_hdr(throwaway["token"]), timeout=30)
        assert me.status_code == 200
        assert me.json().get("pro_active") is True

    def test_theme_gating(self, throwaway, event_loop, db_conn):
        # first, unset pro to test gating
        event_loop.run_until_complete(db_conn.users.update_one({"id": throwaway["id"]}, {"$set": {"pro": None}}))
        r = requests.patch(f"{API}/studio", headers=_hdr(throwaway["token"]),
                           json={"theme": "luxury_gallery"}, timeout=30)
        assert r.status_code == 402, r.text
        r2 = requests.patch(f"{API}/studio", headers=_hdr(throwaway["token"]),
                            json={"theme": "minimal"}, timeout=30)
        assert r2.status_code == 200, r2.text
        # reactivate pro
        end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        event_loop.run_until_complete(db_conn.users.update_one(
            {"id": throwaway["id"]},
            {"$set": {"pro": {"status": "active", "subscription_id": "sub_test",
                              "interval": "month", "amount": 6,
                              "current_period_end": end, "cancel_at_period_end": False}}}))
        r3 = requests.patch(f"{API}/studio", headers=_hdr(throwaway["token"]),
                            json={"theme": "luxury_gallery"}, timeout=30)
        assert r3.status_code == 200, r3.text

    def test_themes_pro_flag(self):
        r = requests.get(f"{API}/studio/themes", timeout=30)
        assert r.status_code == 200
        themes = {t["id"]: t for t in r.json()}
        assert themes["luxury_gallery"]["pro_only"] is True
        assert themes["neon_digital"]["pro_only"] is True
        assert themes["urban_graffiti"]["pro_only"] is False

    def test_boost_placement(self, throwaway, event_loop, db_conn):
        # Ensure throwaway is Pro
        end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        event_loop.run_until_complete(db_conn.users.update_one(
            {"id": throwaway["id"]},
            {"$set": {"pro": {"status": "active", "subscription_id": "sub_test",
                              "interval": "month", "amount": 6,
                              "current_period_end": end, "cancel_at_period_end": False}}}))
        # Insert a live artwork directly for the throwaway artist (Pro)
        art_id = f"art_{uuid.uuid4().hex[:8]}"
        art = {
            "id": art_id, "artist_id": throwaway["id"], "title": "Pro Boost Test",
            "description": "test", "price": 500.0, "currency": "usd",
            "images": ["https://example.com/x.jpg"], "status": "live",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tags": [], "medium": "digital",
        }
        event_loop.run_until_complete(db_conn.artworks.insert_one(art))

        r = requests.get(f"{API}/artworks?limit=50", timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert len(items) > 0
        # first non-sold artwork should be pro_active
        first = items[0]
        assert (first.get("artist") or {}).get("pro_active") is True, f"first item not pro: {first.get('artist')}"
        # artist enrich has founding_member and pro_active fields
        assert "founding_member" in (first.get("artist") or {})

        r2 = requests.get(f"{API}/artworks?limit=50&sort=price_asc", timeout=30)
        assert r2.status_code == 200
        prices = [a["price"] for a in r2.json()]
        assert prices == sorted(prices)


# ---------------- Payouts core (python module) ----------------
class TestPayoutsModule:
    def test_add_business_days_friday_to_monday(self):
        from payouts import add_business_days
        # Friday 2026-01-02
        fri = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
        assert fri.weekday() == 4
        mon = add_business_days(fri, 1)
        assert mon.weekday() == 0

    def test_hold_payouts_marks_held(self, event_loop, db_conn):
        from payouts import hold_payouts
        artist = event_loop.run_until_complete(db_conn.users.find_one({"email": ARTIST[0]}))
        out = event_loop.run_until_complete(hold_payouts([
            {"artist_id": artist["id"], "net": 10, "gross": 12, "status": "pending", "artwork_id": "a"}
        ]))
        assert len(out) == 1
        p = out[0]
        assert p["status"] == "held"
        assert p["hold_reason"] == "awaiting_delivery"
        assert p["release_at"]  # ISO string
        # ~10 business days
        release = datetime.fromisoformat(p["release_at"])
        delta = (release - datetime.now(timezone.utc)).days
        assert 11 <= delta <= 16  # 10 business days ≈ 12-14 calendar days

    def test_release_due_payouts_flow(self, event_loop, db_conn):
        from payouts import release_due_payouts, upcoming_for_artist
        artist = event_loop.run_until_complete(db_conn.users.find_one({"email": ARTIST[0]}))
        oid = f"TEST_ord_{uuid.uuid4().hex[:8]}"
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        order = {
            "id": oid, "buyer_id": "TEST_buyer", "refunded": False,
            "fulfillment": {"status": "pending"},
            "artist_payouts": [{
                "artist_id": artist["id"], "net": 10.0, "gross": 12.0, "status": "held",
                "release_at": past, "hold_reason": "awaiting_delivery", "artwork_id": "a",
            }],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total": 12.0,
        }
        event_loop.run_until_complete(db_conn.orders.insert_one(order))
        try:
            n = event_loop.run_until_complete(release_due_payouts())
            assert n >= 1
            fresh = event_loop.run_until_complete(db_conn.orders.find_one({"id": oid}))
            p = fresh["artist_payouts"][0]
            assert p["status"] in ("pending", "transferred")
            assert p.get("released_at")
            # notification
            note = event_loop.run_until_complete(db_conn.notifications.find_one({
                "user_id": artist["id"], "kind": "payout_released", "order_id": oid}))
            assert note is not None
            # idempotent - second run no-op
            n2 = event_loop.run_until_complete(release_due_payouts())
            fresh2 = event_loop.run_until_complete(db_conn.orders.find_one({"id": oid}))
            assert fresh2["artist_payouts"][0]["status"] == p["status"]
        finally:
            event_loop.run_until_complete(db_conn.orders.delete_one({"id": oid}))
            event_loop.run_until_complete(db_conn.notifications.delete_many({"order_id": oid}))

    def test_upcoming_for_artist_sorted(self, event_loop, db_conn):
        from payouts import upcoming_for_artist
        artist = event_loop.run_until_complete(db_conn.users.find_one({"email": ARTIST[0]}))
        # insert two held orders
        oid1 = f"TEST_ord_{uuid.uuid4().hex[:8]}"
        oid2 = f"TEST_ord_{uuid.uuid4().hex[:8]}"
        far = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
        near = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        for oid, r_at in [(oid1, far), (oid2, near)]:
            event_loop.run_until_complete(db_conn.orders.insert_one({
                "id": oid, "buyer_id": "TEST_b", "refunded": False,
                "fulfillment": {"status": "pending"},
                "artist_payouts": [{"artist_id": artist["id"], "net": 5.0, "gross": 6.0,
                                    "status": "held", "release_at": r_at,
                                    "hold_reason": "awaiting_delivery", "artwork_id": "a"}],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }))
        try:
            rows = event_loop.run_until_complete(upcoming_for_artist(artist["id"]))
            release_ats = [r["release_at"] for r in rows]
            assert release_ats == sorted(release_ats)
        finally:
            event_loop.run_until_complete(db_conn.orders.delete_many({"id": {"$in": [oid1, oid2]}}))

    def test_connect_build_transfer_options_empty(self, event_loop):
        from connect import build_transfer_options
        result = event_loop.run_until_complete(build_transfer_options("some_id", 100.0))
        assert result == {}


# ---------------- Payouts flow via API ----------------
class TestPayoutsAPI:
    @pytest.fixture(scope="class")
    def order_setup(self, event_loop, db_conn):
        artist = event_loop.run_until_complete(db_conn.users.find_one({"email": ARTIST[0]}))
        buyer = event_loop.run_until_complete(db_conn.users.find_one({"email": BUYER[0]}))
        oid = f"TEST_ord_{uuid.uuid4().hex[:8]}"
        rel_at = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        order = {
            "id": oid, "buyer_id": buyer["id"], "refunded": False,
            "fulfillment": {"status": "pending"},
            "artist_payouts": [{
                "artist_id": artist["id"], "net": 10.0, "gross": 12.0,
                "status": "held", "release_at": rel_at,
                "hold_reason": "awaiting_delivery", "artwork_id": "a",
            }],
            "items": [{"artwork_id": "a", "artist_id": artist["id"], "price": 12.0, "quantity": 1}],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total": 12.0,
        }
        event_loop.run_until_complete(db_conn.orders.insert_one(order))
        yield {"oid": oid, "artist_id": artist["id"], "buyer_id": buyer["id"]}
        event_loop.run_until_complete(db_conn.orders.delete_one({"id": oid}))
        event_loop.run_until_complete(db_conn.notifications.delete_many({"order_id": oid}))

    def test_ship_requires_tracking(self, order_setup, artist_token):
        oid = order_setup["oid"]
        r = requests.post(f"{API}/orders/{oid}/ship", headers=_hdr(artist_token),
                          json={"carrier": "UPS", "tracking": ""}, timeout=30)
        assert r.status_code == 422, r.text

    def test_ship_with_tracking(self, order_setup, artist_token):
        oid = order_setup["oid"]
        r = requests.post(f"{API}/orders/{oid}/ship", headers=_hdr(artist_token),
                          json={"carrier": "UPS", "tracking": "TEST123"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["fulfillment"]["status"] == "shipped"

    def test_mark_delivered_moves_release_forward(self, order_setup, buyer_token, event_loop, db_conn):
        oid = order_setup["oid"]
        r = requests.post(f"{API}/orders/{oid}/mark-delivered", headers=_hdr(buyer_token), timeout=30)
        assert r.status_code == 200, r.text
        fresh = event_loop.run_until_complete(db_conn.orders.find_one({"id": oid}))
        p = fresh["artist_payouts"][0]
        assert p["hold_reason"] == "delivered"
        assert p["status"] == "held"
        # release_at ~ now + 2 days
        rel = datetime.fromisoformat(p["release_at"])
        delta_h = (rel - datetime.now(timezone.utc)).total_seconds() / 3600
        assert 40 < delta_h < 56  # ~48 hours

    def test_artist_dashboard_upcoming_payouts(self, order_setup, artist_token):
        r = requests.get(f"{API}/artist/dashboard", headers=_hdr(artist_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        up = data.get("upcoming_payouts") or []
        found = [x for x in up if x.get("order_id") == order_setup["oid"]]
        assert found, f"upcoming_payouts missing our order; got: {[x.get('order_id') for x in up]}"
        assert found[0]["hold_reason"] == "delivered"
        pol = data.get("payout_policy")
        assert pol is not None
        assert pol["delivery_delay_days"] == 2
        assert pol["hold_business_days"] == 10
        assert pol["pro_hold_business_days"] == 5


# ---------------- Regression ----------------
class TestRegression:
    def test_fee_preview(self):
        r = requests.get(f"{API}/settings/fee-preview?gross=100", timeout=30)
        assert r.status_code == 200
        assert r.json()["net"] == 92.8

    def test_waiver_me_founding(self, artist_token):
        r = requests.get(f"{API}/waiver/me", headers=_hdr(artist_token), timeout=30)
        assert r.status_code == 200
        assert r.json().get("founding_member") is True

    def test_gift_unknown_404(self):
        r = requests.get(f"{API}/gift/unknown", timeout=30)
        assert r.status_code == 404
