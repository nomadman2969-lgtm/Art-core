"""Iteration 20 tests: Admin Stripe setup, analytics upgrade (views/saves/growth), gift tickets."""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

def _read_frontend_url():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass
    return os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

BASE_URL = _read_frontend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"

ADMIN = ("admin@artcorestudio.net", os.environ["ADMIN_PASSWORD"])
ARTIST = ("demo.artist@artcorestudio.net", "DemoArtist2026!")
BUYER = ("demo.collector@artcorestudio.net", "DemoCollector2026!")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "house_of_monster")

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"], r.json()["user"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# --------------- Admin Stripe status/config ---------------
class TestAdminStripe:
    def test_status_shape(self):
        token, _ = _login(*ADMIN)
        r = requests.get(f"{API}/admin/stripe/status", headers=_h(token))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["mode"] == "test"
        assert d["live_keys_saved"] is False
        assert isinstance(d.get("connected_artists"), int)
        assert isinstance(d.get("onboarding_url"), str)
        assert "webhook_configured" in d
        # account may or may not fetch depending on stripe env; if present must have id
        if d.get("account"):
            assert isinstance(d["account"].get("id"), str)

    def test_switch_live_without_key(self):
        token, _ = _login(*ADMIN)
        r = requests.patch(f"{API}/admin/stripe/config", json={"mode": "live"}, headers=_h(token))
        assert r.status_code == 400
        assert "live" in r.text.lower()

    def test_bad_secret_key_format(self):
        token, _ = _login(*ADMIN)
        r = requests.patch(f"{API}/admin/stripe/config", json={"live_secret_key": "sk_test_bad"}, headers=_h(token))
        assert r.status_code == 400
        assert "sk_live_" in r.text

    def test_stripe_rejects_fake_live_key(self):
        token, _ = _login(*ADMIN)
        r = requests.patch(f"{API}/admin/stripe/config", json={"live_secret_key": "sk_live_fake123456789"}, headers=_h(token))
        assert r.status_code == 400
        assert "rejected" in r.text.lower() or "stripe" in r.text.lower()

    def test_save_live_publishable(self):
        token, _ = _login(*ADMIN)
        r = requests.patch(f"{API}/admin/stripe/config", json={"live_publishable_key": "pk_live_abc"}, headers=_h(token))
        assert r.status_code == 200
        s = requests.get(f"{API}/admin/stripe/status", headers=_h(token)).json()
        assert s.get("live_publishable_masked")
        # cleanup: remove saved key
        _db.settings.update_one({"id": "global"}, {"$unset": {"stripe_live_publishable_key": ""}})

    def test_non_admin_forbidden(self):
        token, _ = _login(*ARTIST)
        r = requests.get(f"{API}/admin/stripe/status", headers=_h(token))
        assert r.status_code == 403

    def test_mode_remains_test(self):
        token, _ = _login(*ADMIN)
        s = requests.get(f"{API}/admin/stripe/status", headers=_h(token)).json()
        assert s["mode"] == "test"


# --------------- Analytics: views / saves / growth / visits ---------------
class TestAnalytics:
    def test_view_tracking_and_analytics(self):
        atoken, artist = _login(*ARTIST)
        # find an artwork owned by demo artist
        arts_resp = requests.get(f"{API}/artists/{artist['id']}").json()
        arts = arts_resp.get("artworks", [])
        assert isinstance(arts, list) and len(arts) > 0, "demo artist should have artworks"
        art = arts[0]
        aid = art["id"]

        # Baseline analytics
        base = requests.get(f"{API}/studio/analytics/me", headers=_h(atoken)).json()
        base_views = base.get("total_views", 0)
        base_visits = base.get("visits_14d", 0)

        # Two unauth GETs on artwork (should increment)
        for _ in range(2):
            r = requests.get(f"{API}/artworks/{aid}")
            assert r.status_code == 200

        # Also: viewing own art logged in should NOT increment
        r = requests.get(f"{API}/artworks/{aid}", headers=_h(atoken))
        assert r.status_code == 200

        after = requests.get(f"{API}/studio/analytics/me", headers=_h(atoken)).json()
        # views increased by exactly 2 (own-view skipped)
        assert after["total_views"] - base_views >= 2, f"expected +2 views, base={base_views} after={after['total_views']}"

        # Fields present
        for k in ["total_saves", "follower_growth", "visit_series", "new_followers_30d", "visits_14d", "top_viewed"]:
            assert k in after, f"missing {k}"
        assert len(after["follower_growth"]) == 8
        for g in after["follower_growth"]:
            assert "label" in g and "followers" in g
        assert len(after["visit_series"]) == 14
        for v in after["visit_series"]:
            assert "label" in v and "visits" in v

        # top_viewed must contain that artwork with views>=2
        top = [t for t in after["top_viewed"] if t["id"] == aid]
        assert top, f"artwork {aid} missing from top_viewed"
        assert top[0]["views"] >= 2
        for t in after["top_viewed"]:
            for k in ["views", "saves", "likes"]:
                assert k in t

    def test_studio_visit_logging(self):
        atoken, artist = _login(*ARTIST)
        base = requests.get(f"{API}/studio/analytics/me", headers=_h(atoken)).json()
        base_visits = base.get("visits_14d", 0)
        base_last = base["visit_series"][-1]["visits"]

        # Unauth GET studio page
        r = requests.get(f"{API}/studio/{artist['id']}")
        assert r.status_code == 200

        after = requests.get(f"{API}/studio/analytics/me", headers=_h(atoken)).json()
        assert after["visits_14d"] >= base_visits + 1
        assert after["visit_series"][-1]["visits"] >= base_last + 1


# --------------- Gift Tickets ---------------
def _ensure_paid_event(atoken):
    """Find or create a paid upcoming event hosted by demo artist."""
    events = requests.get(f"{API}/events").json()
    for e in events:
        if not e.get("is_free") and e.get("ticket_price", 0) > 0 and not e.get("cancelled"):
            return e
    # create one
    from datetime import timedelta
    start = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    payload = {
        "title": f"TEST_Paid_{uuid.uuid4().hex[:6]}",
        "description": "test paid event",
        "start_at": start,
        "location": {"lat": 40.7, "lng": -74.0, "city": "Testville", "address": "1 Test St"},
        "is_free": False,
        "ticket_price": 25.0,
        "max_capacity": 100,
    }
    r = requests.post(f"{API}/events", json=payload, headers=_h(atoken))
    assert r.status_code in (200, 201), r.text
    return r.json()


class TestGiftTicket:
    def test_gift_checkout_paid_event(self):
        atoken, _ = _login(*ARTIST)
        ev = _ensure_paid_event(atoken)
        btoken, _ = _login(*BUYER)
        r = requests.post(
            f"{API}/payments/events/{ev['id']}/gift",
            json={"origin_url": BASE_URL, "recipient_email": "friend.test@example.com",
                  "recipient_name": "Friend", "message": "Enjoy!"},
            headers=_h(btoken),
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "stripe.com" in d["checkout_url"]
        assert abs(d["amount"] - float(ev["ticket_price"])) < 0.001
        tx = _db.payment_transactions.find_one({"session_id": d["session_id"]})
        assert tx and tx["kind"] == "event_ticket_gift"

    def test_gift_invalid_email(self):
        atoken, _ = _login(*ARTIST)
        ev = _ensure_paid_event(atoken)
        btoken, _ = _login(*BUYER)
        r = requests.post(
            f"{API}/payments/events/{ev['id']}/gift",
            json={"origin_url": BASE_URL, "recipient_email": "notanemail"},
            headers=_h(btoken),
        )
        assert r.status_code == 400

    def test_gift_free_event_rejected(self):
        atoken, _ = _login(*ARTIST)
        # create a free event
        from datetime import timedelta
        start = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
        r = requests.post(f"{API}/events", json={
            "title": f"TEST_Free_{uuid.uuid4().hex[:6]}", "description": "free",
            "start_at": start, "location": {"lat": 40.7, "lng": -74.0, "city": "X"},
            "is_free": True,
        }, headers=_h(atoken))
        assert r.status_code in (200, 201)
        free = r.json()
        btoken, _ = _login(*BUYER)
        rr = requests.post(
            f"{API}/payments/events/{free['id']}/gift",
            json={"origin_url": BASE_URL, "recipient_email": "friend.test@example.com"},
            headers=_h(btoken),
        )
        assert rr.status_code == 400
        # cleanup
        _db.events.delete_one({"id": free["id"]})

    def test_gift_fulfilment_end_to_end(self):
        atoken, artist = _login(*ARTIST)
        ev = _ensure_paid_event(atoken)
        # Insert a fake fulfilled RSVP directly
        token = f"testtoken_{uuid.uuid4().hex[:8]}"
        rsvp = {
            "id": str(uuid.uuid4()), "event_id": ev["id"],
            "user_id": None, "user_name": "Friend",
            "paid": True, "amount": float(ev["ticket_price"]),
            "session_id": f"cs_test_fake_{uuid.uuid4().hex[:8]}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "gift": True, "gift_email": "friend.test@example.com",
            "gift_token": token, "gifted_by_name": "Tester",
        }
        _db.event_rsvps.insert_one(dict(rsvp))
        try:
            # 1. Public gift view
            r = requests.get(f"{API}/events/gift/{token}")
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["event"]["title"] == ev["title"]
            assert d["user_name"] == "Friend"
            assert d["qr_image"].startswith("data:image/png;base64,")
            assert d["qr_payload"] == f"artcore:ticket:{rsvp['id']}:{ev['id']}"
            assert d["claimed"] is False

            # 2. QR png
            r = requests.get(f"{API}/events/gift/{token}/qr.png")
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("image/png")

            # 3. Unknown token
            r = requests.get(f"{API}/events/gift/unknown_bogus_xyz")
            assert r.status_code == 404

            # 4. Host check-in with QR payload
            payload = f"artcore:ticket:{rsvp['id']}:{ev['id']}"
            r = requests.post(f"{API}/events/{ev['id']}/check-in",
                              json={"qr_payload": payload}, headers=_h(atoken))
            assert r.status_code == 200, r.text
            assert r.json().get("ok") is True
            assert r.json().get("user_name") == "Friend"

            # 5. Register a user with the recipient email → rsvp claim
            new_email = "friend.test@example.com"
            # remove any pre-existing user with that email
            _db.users.delete_many({"email": new_email})
            reg = requests.post(f"{API}/auth/register", json={
                "email": new_email, "password": "Friend2026!",
                "name": "Friend Tester", "role": "buyer",
            })
            assert reg.status_code == 200, reg.text
            new_user_id = reg.json()["user"]["id"]
            new_token = reg.json()["token"]
            updated = _db.event_rsvps.find_one({"gift_token": token})
            assert updated.get("user_id") == new_user_id

            # 6. New user's tickets endpoint includes the event
            r = requests.get(f"{API}/events/mine/tickets", headers=_h(new_token))
            assert r.status_code == 200, r.text
            titles = [t.get("event", {}).get("title") for t in r.json()]
            assert ev["title"] in titles
        finally:
            _db.event_rsvps.delete_one({"gift_token": token})
            _db.users.delete_many({"email": "friend.test@example.com"})


@pytest.fixture(scope="session", autouse=True)
def _cleanup_at_end():
    yield
    # remove any TEST_ events
    _db.events.delete_many({"title": {"$regex": "^TEST_"}})
    # ensure mode is test
    _db.settings.update_one({"id": "global"}, {"$unset": {
        "stripe_live_secret_key": "", "stripe_live_publishable_key": "",
        "stripe_live_webhook_secret": "", "stripe_mode": "",
    }})
