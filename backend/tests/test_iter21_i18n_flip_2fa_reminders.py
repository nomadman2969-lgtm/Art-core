"""Iter21: i18n language, Flip Commissions, 2FA (TOTP + email), gift reminder sweep."""
import os
import time
import uuid
import asyncio
import pytest
import requests
import pyotp

def _get_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        for line in open("/app/frontend/.env"):
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return ""

BASE = _get_base()

# Load backend/.env into environment for tests that import backend modules
try:
    for _line in open("/app/backend/.env"):
        _line = _line.strip()
        if _line and "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v.strip().strip('"').strip("'"))
except Exception:
    pass
API = f"{BASE}/api"

ARTIST_EMAIL = "demo.artist@artcorestudio.net"
ARTIST_PW = "DemoArtist2026!"
COLLECTOR_EMAIL = "demo.collector@artcorestudio.net"
COLLECTOR_PW = "DemoCollector2026!"
ADMIN_EMAIL = "monster@houseofmonster.com"
ADMIN_PW = "MonsterAdmin2026!"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def collector_tok():
    return _login(COLLECTOR_EMAIL, COLLECTOR_PW)["token"]


@pytest.fixture(scope="module")
def artist():
    d = _login(ARTIST_EMAIL, ARTIST_PW)
    return d["token"], d["user"]["id"]


@pytest.fixture(scope="module")
def admin_tok():
    return _login(ADMIN_EMAIL, ADMIN_PW)["token"]


# =============== i18n backend =====================
class TestI18nBackend:
    def test_patch_language_and_get_me(self, collector_tok):
        r = requests.patch(f"{API}/auth/me", json={"language": "fr"}, headers=_hdr(collector_tok), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("language") == "fr"
        r2 = requests.get(f"{API}/auth/me", headers=_hdr(collector_tok), timeout=20)
        assert r2.status_code == 200
        assert r2.json().get("language") == "fr"
        # reset
        rr = requests.patch(f"{API}/auth/me", json={"language": "en"}, headers=_hdr(collector_tok), timeout=20)
        assert rr.status_code == 200 and rr.json().get("language") == "en"


# =============== Flip Commissions =====================
class TestFlip:
    def test_flip_artists_lists_demo(self, artist):
        r = requests.get(f"{API}/commissions/flip/artists", timeout=20)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and len(arr) > 0
        # demo artist should be in list
        ids = [a["id"] for a in arr]
        assert artist[1] in ids, f"demo artist {artist[1]} not in {ids}"
        for a in arr:
            for k in ("id", "name", "pieces", "types", "sample"):
                assert k in a

    def test_create_flip_commission_ok(self, collector_tok, artist):
        payload = {
            "artist_id": artist[1],
            "subject": "TEST_flip dresser refresh",
            "instructions": "Please strip and refinish top",
            "budget": 300,
            "reference_images": ["x.jpg"],
            "kind": "flip",
            "furniture": {"furniture_type": "dresser", "condition": "worn", "handoff": "dropoff", "city": "Austin"},
        }
        r = requests.post(f"{API}/commissions", json=payload, headers=_hdr(collector_tok), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["kind"] == "flip"
        assert d["furniture"]["furniture_type"] == "dresser"
        assert d["furniture"]["handoff"] == "dropoff"
        cid = d["id"]
        # GET
        g = requests.get(f"{API}/commissions/{cid}", headers=_hdr(collector_tok), timeout=20)
        assert g.status_code == 200
        gd = g.json()
        assert gd["kind"] == "flip" and gd["furniture"]["furniture_type"] == "dresser"
        pytest.flip_cid = cid

    def test_flip_requires_photos(self, collector_tok, artist):
        payload = {
            "artist_id": artist[1], "subject": "no photo", "instructions": "x", "budget": 200,
            "reference_images": [], "kind": "flip",
            "furniture": {"furniture_type": "chair", "handoff": "dropoff"},
        }
        r = requests.post(f"{API}/commissions", json=payload, headers=_hdr(collector_tok), timeout=20)
        assert r.status_code == 400, r.text

    def test_flip_requires_furniture(self, collector_tok, artist):
        payload = {
            "artist_id": artist[1], "subject": "no furn", "instructions": "x", "budget": 200,
            "reference_images": ["a.jpg"], "kind": "flip",
        }
        r = requests.post(f"{API}/commissions", json=payload, headers=_hdr(collector_tok), timeout=20)
        assert r.status_code == 400

    def test_plain_art_still_works(self, collector_tok, artist):
        payload = {
            "artist_id": artist[1], "subject": "TEST_art commission", "instructions": "portrait",
            "budget": 500, "reference_images": [],
        }
        r = requests.post(f"{API}/commissions", json=payload, headers=_hdr(collector_tok), timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["kind"] == "art"
        assert d.get("furniture") in (None,)

    def test_deposit_escrow_after_accept(self, collector_tok, artist):
        cid = getattr(pytest, "flip_cid", None)
        assert cid, "flip commission created earlier"
        # artist accepts
        atok = artist[0]
        r = requests.post(f"{API}/commissions/{cid}/respond", json={"action": "accept"}, headers=_hdr(atok), timeout=20)
        assert r.status_code == 200, r.text
        # buyer initiates deposit
        r2 = requests.post(f"{API}/payments/commissions/{cid}/deposit", json={"origin_url": BASE}, headers=_hdr(collector_tok), timeout=30)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert "checkout_url" in d and d["checkout_url"].startswith("http")


# =============== 2FA TOTP =====================
def _register_throwaway(role="buyer"):
    email = f"twofa_{uuid.uuid4().hex[:10]}@example.com"
    pw = "TestPass2026!"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "2FA Tester", "role": role}, timeout=20)
    assert r.status_code == 200, r.text
    return email, pw, r.json()["token"], r.json()["user"]["id"]


class TestTwofaTotp:
    def test_full_totp_flow(self):
        email, pw, tok, uid = _register_throwaway()
        # setup
        r = requests.post(f"{API}/auth/2fa/setup", json={"method": "totp"}, headers=_hdr(tok), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["method"] == "totp"
        secret = d["secret"]
        assert d["otpauth_uri"].startswith("otpauth://")
        assert d["qr_image"] and d["qr_image"].startswith("data:image/png;base64,")
        # enable
        code = pyotp.TOTP(secret).now()
        r = requests.post(f"{API}/auth/2fa/enable", json={"code": code}, headers=_hdr(tok), timeout=20)
        assert r.status_code == 200, r.text
        e = r.json()
        assert e["enabled"] is True and e["method"] == "totp"
        recovery = e["recovery_codes"]
        assert isinstance(recovery, list) and len(recovery) == 8

        # login → requires_2fa
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
        assert r.status_code == 200
        ch = r.json()
        assert ch.get("requires_2fa") is True and ch["method"] == "totp" and ch["challenge_token"]

        # wrong code
        rw = requests.post(f"{API}/auth/2fa/verify-login", json={"challenge_token": ch["challenge_token"], "code": "000000"}, timeout=20)
        assert rw.status_code == 401

        # correct code
        time.sleep(1)
        code2 = pyotp.TOTP(secret).now()
        rc = requests.post(f"{API}/auth/2fa/verify-login", json={"challenge_token": ch["challenge_token"], "code": code2}, timeout=20)
        assert rc.status_code == 200, rc.text
        vd = rc.json()
        assert vd["token"] and vd["user"]["twofa_enabled"] is True
        new_tok = vd["token"]

        # login again → challenge again
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
        ch2 = r.json()
        # use recovery code
        rc2 = requests.post(f"{API}/auth/2fa/verify-login", json={"challenge_token": ch2["challenge_token"], "code": recovery[0]}, timeout=20)
        assert rc2.status_code == 200, rc2.text
        # status: 7 left
        rs = requests.get(f"{API}/auth/2fa/status", headers=_hdr(rc2.json()["token"]), timeout=20)
        assert rs.status_code == 200
        assert rs.json()["recovery_codes_left"] == 7

        # reuse recovery → 401
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
        ch3 = r.json()
        rc3 = requests.post(f"{API}/auth/2fa/verify-login", json={"challenge_token": ch3["challenge_token"], "code": recovery[0]}, timeout=20)
        assert rc3.status_code == 401

        # disable — wrong password
        code3 = pyotp.TOTP(secret).now()
        rd = requests.post(f"{API}/auth/2fa/disable", json={"password": "wrong", "code": code3}, headers=_hdr(new_tok), timeout=20)
        assert rd.status_code == 401

        # disable correctly
        time.sleep(1)
        code4 = pyotp.TOTP(secret).now()
        rd = requests.post(f"{API}/auth/2fa/disable", json={"password": pw, "code": code4}, headers=_hdr(new_tok), timeout=20)
        assert rd.status_code == 200 and rd.json()["enabled"] is False

        # login → direct token
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
        assert r.status_code == 200
        assert r.json().get("token") and not r.json().get("requires_2fa")

    def test_enable_without_setup(self):
        _, _, tok, _ = _register_throwaway()
        r = requests.post(f"{API}/auth/2fa/enable", json={"code": "123456"}, headers=_hdr(tok), timeout=20)
        assert r.status_code == 400


# =============== 2FA Email =====================
class TestTwofaEmail:
    def test_setup_email_writes_hash(self):
        email, pw, tok, uid = _register_throwaway()
        r = requests.post(f"{API}/auth/2fa/setup", json={"method": "email"}, headers=_hdr(tok), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["method"] == "email"
        assert d["sent_to"] == email
        # verify hash exists in Mongo
        from motor.motor_asyncio import AsyncIOMotorClient
        async def check():
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db = client[os.environ.get("DB_NAME", "house_of_monster")]
            u = await db.users.find_one({"id": uid})
            client.close()
            return u
        u = asyncio.get_event_loop().run_until_complete(check())
        assert u.get("twofa_email_code_hash"), "email code hash not stored"
        assert u.get("twofa_email_code_exp"), "email code exp not set"

    def test_resend_for_email_2fa_user(self):
        """Directly set user as email-2fa enabled in mongo and test /resend with challenge_token."""
        email, pw, tok, uid = _register_throwaway()
        # flip user to email-2fa enabled in mongo
        from motor.motor_asyncio import AsyncIOMotorClient
        async def prep():
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db = client[os.environ.get("DB_NAME", "house_of_monster")]
            await db.users.update_one({"id": uid}, {"$set": {"twofa_enabled": True, "twofa_method": "email"}})
            client.close()
        asyncio.get_event_loop().run_until_complete(prep())

        # login → challenge
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
        assert r.status_code == 200
        ch = r.json()
        assert ch.get("requires_2fa") and ch["method"] == "email"
        tok_ch = ch["challenge_token"]
        # resend
        rr = requests.post(f"{API}/auth/2fa/resend", json={"challenge_token": tok_ch}, timeout=20)
        assert rr.status_code == 200
        assert rr.json().get("sent") is True


# =============== Gift Reminder Sweep =====================
class TestReminderSweep:
    def test_reminder_marks_event_and_rsvp(self, artist):
        """Create event ~23.5h out, insert gift rsvp, run check_event_reminders, verify markers."""
        from datetime import datetime, timedelta, timezone
        atok = artist[0]
        start_at = (datetime.now(timezone.utc) + timedelta(hours=23, minutes=30)).isoformat()
        end_at = (datetime.now(timezone.utc) + timedelta(hours=25)).isoformat()
        ev = {
            "title": "TEST_reminder event",
            "description": "test",
            "kind": "other",
            "start_at": start_at,
            "end_at": end_at,
            "location": {"city": "Austin", "address": "Test", "lat": 30.26, "lng": -97.74},
            "ticket_price": 10,
            "capacity": 50,
            "reminders_enabled": True,
        }
        r = requests.post(f"{API}/events", json=ev, headers=_hdr(atok), timeout=20)
        assert r.status_code == 200, r.text
        ev_id = r.json()["id"]

        # insert gift rsvp
        from motor.motor_asyncio import AsyncIOMotorClient
        rsvp_id = f"TEST_rsvp_{uuid.uuid4().hex[:8]}"
        async def run():
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db = client[os.environ.get("DB_NAME", "house_of_monster")]
            await db.event_rsvps.insert_one({
                "id": rsvp_id, "event_id": ev_id, "user_id": None,
                "gift": True, "gift_email": "friend.rem@example.com", "gift_token": "remtok1",
                "paid": True, "refunded": False, "created_at": datetime.now(timezone.utc).isoformat(),
            })
            # unset markers on event (in case default)
            await db.events.update_one({"id": ev_id}, {"$unset": {"reminder_24h_sent": "", "reminder_1h_sent": ""}})
            import sys
            sys.path.insert(0, "/app/backend")
            from events import check_event_reminders
            await check_event_reminders()
            ev1 = await db.events.find_one({"id": ev_id})
            rsvp1 = await db.event_rsvps.find_one({"id": rsvp_id})
            # second run — should be idempotent
            await check_event_reminders()
            ev2 = await db.events.find_one({"id": ev_id})
            rsvp2 = await db.event_rsvps.find_one({"id": rsvp_id})
            # cleanup
            await db.event_rsvps.delete_one({"id": rsvp_id})
            await db.events.delete_one({"id": ev_id})
            client.close()
            return ev1, rsvp1, ev2, rsvp2
        ev1, rsvp1, ev2, rsvp2 = asyncio.get_event_loop().run_until_complete(run())
        assert ev1.get("reminder_24h_sent"), "event reminder_24h_sent not set"
        assert rsvp1.get("gift_reminder_sent"), "rsvp gift_reminder_sent not set"
        # idempotent — timestamp unchanged
        assert ev1["reminder_24h_sent"] == ev2["reminder_24h_sent"]
        assert rsvp1["gift_reminder_sent"] == rsvp2["gift_reminder_sent"]


# =============== Regression =====================
class TestRegression:
    def test_fee_preview(self):
        r = requests.get(f"{API}/settings/fee-preview", params={"gross": 100}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert abs(d["net"] - 92.8) < 0.05

    def test_gift_unknown_token(self):
        r = requests.get(f"{API}/events/gift/unknown", timeout=20)
        assert r.status_code == 404

    def test_admin_stripe_status(self, admin_tok):
        r = requests.get(f"{API}/admin/stripe/status", headers=_hdr(admin_tok), timeout=20)
        assert r.status_code == 200
        assert r.json().get("mode") == "test"
