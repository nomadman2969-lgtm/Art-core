"""Iteration 22: Founding-artist fee waiver, Flip Quotes, Trusted Devices, Wallet Pass, i18n extension, Regression."""
import os
import sys
sys.path.insert(0, "/app/backend")
import io
import time
import uuid
import struct
import asyncio
import pytest
import requests
import pyotp
from pathlib import Path

# Load backend .env (tests aren't spawned by uvicorn)
_env = Path("/app/backend/.env")
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if "REACT_APP_BACKEND_URL" in os.environ else "https://monster-curated.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN = ("monster@houseofmonster.com", "MonsterAdmin2026!")
ARTIST = ("demo.artist@artcorestudio.net", "DemoArtist2026!")
COLLECTOR = ("demo.collector@artcorestudio.net", "DemoCollector2026!")


# ---------- helpers ----------
def login(email: str, password: str, device_token: str = None) -> dict:
    body = {"email": email, "password": password}
    if device_token:
        body["device_token"] = device_token
    r = requests.post(f"{API}/auth/login", json=body, timeout=20)
    return r


def token_of(email: str, password: str) -> str:
    r = login(email, password)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def register_throwaway(role: str = "artist", tag: str = "iter22") -> tuple:
    email = f"TEST_{tag}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Passw0rd!123"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": f"Test {role}", "role": role}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    return email, pw, data["token"], data["user"]["id"]


# ================================================================
# WAIVER — Backend
# ================================================================
class TestWaiverBackend:
    def test_settings_exposes_waiver(self):
        r = requests.get(f"{API}/settings", timeout=15)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s.get("waiver_enabled") is True
        assert s.get("waiver_days") == 30
        assert s.get("waiver_max_sales") == 5

    def test_new_artist_gets_waiver(self):
        _, _, tok, uid = register_throwaway("artist")
        r = requests.get(f"{API}/waiver/me", headers=hdr(tok), timeout=15)
        assert r.status_code == 200, r.text
        w = r.json()
        assert w["active"] is True
        assert 29 <= w["days_left"] <= 30
        assert w["sales_left"] == 5
        # Save for the re-register test
        pytest.artist_email_for_reregister = _[0] if isinstance(_, tuple) else None

    def test_new_buyer_no_waiver(self):
        _, _, tok, _uid = register_throwaway("buyer")
        r = requests.get(f"{API}/waiver/me", headers=hdr(tok), timeout=15)
        assert r.status_code == 200
        assert r.json()["active"] is False

    def test_reregister_does_not_regrant_waiver(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        email = f"TEST_reg_{uuid.uuid4().hex[:8]}@example.com"
        pw = "Passw0rd!123"
        # Register artist
        r1 = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "Reg Test", "role": "artist"}, timeout=20)
        assert r1.status_code == 200
        tok1 = r1.json()["token"]
        assert requests.get(f"{API}/waiver/me", headers=hdr(tok1), timeout=15).json()["active"] is True

        # Delete user doc (KEEP waiver_grants)
        async def _del():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            await db.users.delete_one({"email": email.lower()})
        asyncio.get_event_loop().run_until_complete(_del())

        # Re-register with same email
        r2 = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "Reg Test", "role": "artist"}, timeout=20)
        assert r2.status_code == 200
        tok2 = r2.json()["token"]
        w = requests.get(f"{API}/waiver/me", headers=hdr(tok2), timeout=15).json()
        assert w["active"] is False, f"waiver should NOT be re-granted on re-register, got {w}"

    def test_admin_grant_extends_and_revoke_and_settings_patch(self):
        _, _, _tok, uid = register_throwaway("artist", tag="admin")
        admin_tok = token_of(*ADMIN)

        # Extend by 30 days
        r = requests.post(f"{API}/admin/waiver/{uid}", json={"days": 30}, headers=hdr(admin_tok), timeout=15)
        assert r.status_code == 200, r.text
        w = r.json()
        assert w["active"] is True
        assert w["days_left"] >= 30
        assert w["sales_left"] == 5

        # non-admin → 403
        buyer_tok = token_of(*COLLECTOR)
        r_forbidden = requests.post(f"{API}/admin/waiver/{uid}", json={"days": 30}, headers=hdr(buyer_tok), timeout=15)
        assert r_forbidden.status_code == 403

        # Revoke
        rd = requests.delete(f"{API}/admin/waiver/{uid}", headers=hdr(admin_tok), timeout=15)
        assert rd.status_code == 200
        # Confirm via /waiver/me needs the artist token
        art_tok = _tok
        w2 = requests.get(f"{API}/waiver/me", headers=hdr(art_tok), timeout=15).json()
        assert w2["active"] is False

        # PATCH settings waiver_days 45 → GET returns 45 → restore 30
        p = requests.patch(f"{API}/admin/settings", json={"waiver_days": 45}, headers=hdr(admin_tok), timeout=15)
        assert p.status_code == 200, p.text
        s = requests.get(f"{API}/settings", timeout=15).json()
        assert s["waiver_days"] == 45
        # restore
        requests.patch(f"{API}/admin/settings", json={"waiver_days": 30}, headers=hdr(admin_tok), timeout=15)
        s2 = requests.get(f"{API}/settings", timeout=15).json()
        assert s2["waiver_days"] == 30

    def test_settings_for_seller_zeroes_commission(self):
        """Unit-level via direct import."""
        from motor.motor_asyncio import AsyncIOMotorClient
        _, _, _t, uid = register_throwaway("artist", tag="unit")

        async def _run():
            from waiver import settings_for_seller
            from payments import get_settings
            settings = await get_settings()
            out = await settings_for_seller(uid, settings)
            return out
        out = asyncio.get_event_loop().run_until_complete(_run())
        assert out.get("fee_waived") is True
        assert float(out.get("commission_percent")) == 0.0

    def test_check_waiver_reminders_7d_idempotent(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        from datetime import datetime, timedelta, timezone
        _, _, _t, uid = register_throwaway("artist", tag="rem")

        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            # Force fee_waiver_until = 6 days out
            until = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
            await db.users.update_one({"id": uid}, {"$set": {"fee_waiver_until": until}, "$unset": {"waiver_reminder_7d_sent": "", "waiver_reminder_1d_sent": ""}})
            from waiver import check_waiver_reminders
            await check_waiver_reminders()
            u1 = await db.users.find_one({"id": uid})
            n1 = await db.notifications.count_documents({"user_id": uid, "kind": "waiver_ending"})
            # Second run → no duplicate
            await check_waiver_reminders()
            n2 = await db.notifications.count_documents({"user_id": uid, "kind": "waiver_ending"})
            return u1.get("waiver_reminder_7d_sent"), n1, n2
        sent, n1, n2 = asyncio.get_event_loop().run_until_complete(_run())
        assert sent, "7d reminder marker must be set"
        assert n1 == 1, f"expected 1 notification, got {n1}"
        assert n2 == 1, f"second sweep must be idempotent, got {n2}"


# ================================================================
# FLIP QUOTES
# ================================================================
class TestFlipQuotes:
    def test_flip_quote_flow(self):
        buyer_tok = token_of(*COLLECTOR)
        artist_tok = token_of(*ARTIST)
        # Get demo artist id
        me_art = requests.get(f"{API}/auth/me", headers=hdr(artist_tok), timeout=15).json()
        artist_id = me_art["id"]

        # Create flip commission
        payload = {
            "artist_id": artist_id,
            "subject": "TEST_flip_quote table",
            "budget": 300,
            "instructions": "Refinish this piece",
            "reference_images": ["x.jpg"],
            "kind": "flip",
            "furniture": {"furniture_type": "table", "dimensions": "60x30", "handoff": "dropoff"},
        }
        r = requests.post(f"{API}/commissions", json=payload, headers=hdr(buyer_tok), timeout=20)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]

        # Artist responds with counter (quote)
        r2 = requests.post(f"{API}/commissions/{cid}/respond", json={
            "action": "counter", "counter_amount": 420, "message": "Prep, sand, 2 coats, sealed",
            "sketch_image": "sketch.jpg", "timeline_days": 14,
        }, headers=hdr(artist_tok), timeout=15)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["status"] == "counter"
        q = d.get("quote")
        assert q, "quote must be present"
        assert q["amount"] == 420
        assert q["sketch_image"] == "sketch.jpg"
        assert q["note"] == "Prep, sand, 2 coats, sealed"
        assert q["timeline_days"] == 14

        # Buyer accepts counter
        r3 = requests.post(f"{API}/commissions/{cid}/buyer-action", json={"action": "accept_counter"}, headers=hdr(buyer_tok), timeout=15)
        assert r3.status_code == 200, r3.text
        d3 = r3.json()
        assert d3["status"] == "in_progress"
        assert float(d3["budget"]) == 420.0

        # cleanup
        from motor.motor_asyncio import AsyncIOMotorClient
        async def _clean():
            c = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            await c.commissions.delete_one({"id": cid})
        asyncio.get_event_loop().run_until_complete(_clean())


# ================================================================
# TRUSTED DEVICES
# ================================================================
class TestTrustedDevices:
    def test_full_trusted_device_flow(self):
        email, pw, tok, uid = register_throwaway("buyer", tag="td")
        # Enroll TOTP
        r = requests.post(f"{API}/auth/2fa/setup", json={"method": "totp"}, headers=hdr(tok), timeout=15)
        assert r.status_code == 200, r.text
        secret = r.json()["secret"]
        totp = pyotp.TOTP(secret)
        r2 = requests.post(f"{API}/auth/2fa/enable", json={"code": totp.now()}, headers=hdr(tok), timeout=15)
        assert r2.status_code == 200, r2.text

        # Login → requires 2FA
        rl = login(email, pw)
        assert rl.status_code == 200
        jl = rl.json()
        assert jl.get("requires_2fa") is True
        challenge = jl["challenge_token"]

        # Verify with remember_device
        time.sleep(1)
        rv = requests.post(f"{API}/auth/2fa/verify-login", json={
            "challenge_token": challenge, "code": totp.now(), "remember_device": True, "device_label": "Test laptop",
        }, timeout=15)
        assert rv.status_code == 200, rv.text
        jv = rv.json()
        assert "token" in jv
        assert "device_token" in jv
        assert "device_expires_at" in jv
        device_token = jv["device_token"]
        new_tok = jv["token"]

        # Login with device_token → no 2fa
        rl2 = login(email, pw, device_token=device_token)
        assert rl2.status_code == 200
        jl2 = rl2.json()
        assert "token" in jl2 and not jl2.get("requires_2fa"), f"device_token should skip 2FA: {jl2}"

        # Login with bogus token → requires_2fa
        rl3 = login(email, pw, device_token="bogus_device_token_xxx")
        jl3 = rl3.json()
        assert jl3.get("requires_2fa") is True

        # List devices
        rd = requests.get(f"{API}/auth/2fa/devices", headers=hdr(new_tok), timeout=15)
        assert rd.status_code == 200
        devs = rd.json()
        assert len(devs) == 1
        assert devs[0]["label"] == "Test laptop"
        dev_id = devs[0]["id"]

        # Revoke by id
        rrv = requests.delete(f"{API}/auth/2fa/devices/{dev_id}", headers=hdr(new_tok), timeout=15)
        assert rrv.status_code == 200

        # Login with old device_token → requires_2fa
        rl4 = login(email, pw, device_token=device_token)
        assert rl4.json().get("requires_2fa") is True

        # Enroll another → then delete all
        time.sleep(1)
        c2 = login(email, pw).json()["challenge_token"]
        rv2 = requests.post(f"{API}/auth/2fa/verify-login", json={
            "challenge_token": c2, "code": totp.now(), "remember_device": True, "device_label": "phone",
        }, timeout=15)
        assert rv2.status_code == 200
        tok2 = rv2.json()["token"]
        assert len(requests.get(f"{API}/auth/2fa/devices", headers=hdr(tok2), timeout=15).json()) == 1

        rall = requests.delete(f"{API}/auth/2fa/devices", headers=hdr(tok2), timeout=15)
        assert rall.status_code == 200
        assert requests.get(f"{API}/auth/2fa/devices", headers=hdr(tok2), timeout=15).json() == []


# ================================================================
# WALLET PASS
# ================================================================
class TestWalletPass:
    def test_wallet_pass_flows(self):
        artist_tok = token_of(*ARTIST)
        collector_tok = token_of(*COLLECTOR)

        # Create free event
        from datetime import datetime, timedelta, timezone
        start = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        payload = {
            "title": "TEST_wallet_pass_event",
            "description": "Wallet pass test event",
            "category": "gallery_opening",
            "location": {"lat": 40.7, "lng": -74.0, "address": "1 Test St", "city": "NYC"},
            "start_at": start,
            "is_free": True,
        }
        r = requests.post(f"{API}/events", json=payload, headers=hdr(artist_tok), timeout=20)
        assert r.status_code == 200, r.text
        event_id = r.json()["id"]

        # RSVP as collector
        rr = requests.post(f"{API}/events/{event_id}/rsvp", headers=hdr(collector_tok), timeout=15)
        assert rr.status_code == 200

        # Get pass
        rp = requests.get(f"{API}/events/{event_id}/my-ticket/pass.png", headers=hdr(collector_tok), timeout=30)
        assert rp.status_code == 200, rp.text[:200]
        assert rp.headers.get("content-type") == "image/png"
        assert "attachment" in (rp.headers.get("content-disposition") or "")
        assert len(rp.content) > 20_000, f"expected >20KB, got {len(rp.content)}"
        assert rp.content[:8] == b"\x89PNG\r\n\x1a\n"
        # Decode dimensions
        w, h = struct.unpack(">II", rp.content[16:24])
        assert (w, h) == (1080, 1920), f"got {w}x{h}"

        # Gift RSVP
        from motor.motor_asyncio import AsyncIOMotorClient
        gift_token = f"walltok_{uuid.uuid4().hex[:6]}"
        async def _mk_gift():
            c = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            await c.event_rsvps.insert_one({
                "id": str(uuid.uuid4()),
                "event_id": event_id,
                "user_id": None,
                "user_name": "Gift Guest",
                "gift_token": gift_token,
                "gift_email": "gift@example.com",
                "paid": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        asyncio.get_event_loop().run_until_complete(_mk_gift())

        rg = requests.get(f"{API}/events/gift/{gift_token}/pass.png", timeout=30)
        assert rg.status_code == 200, rg.text[:200]
        assert rg.headers.get("content-type") == "image/png"
        assert rg.content[:8] == b"\x89PNG\r\n\x1a\n"

        # Unknown token 404
        r404 = requests.get(f"{API}/events/gift/unknown_bogus_xyz/pass.png", timeout=15)
        assert r404.status_code == 404

        # cleanup
        async def _clean():
            c = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            await c.event_rsvps.delete_many({"event_id": event_id})
            await c.events.delete_one({"id": event_id})
        asyncio.get_event_loop().run_until_complete(_clean())


# ================================================================
# REGRESSION
# ================================================================
class TestRegression:
    def test_fee_preview(self):
        r = requests.get(f"{API}/settings/fee-preview?gross=100", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert abs(float(d.get("net")) - 92.8) < 0.05, f"net should be 92.8, got {d}"

    def test_demo_login_direct_token(self):
        for email, pw in (ARTIST, COLLECTOR):
            r = login(email, pw)
            assert r.status_code == 200, r.text
            j = r.json()
            assert "token" in j and not j.get("requires_2fa"), f"{email} should return token directly"

    def test_flip_artists_public(self):
        r = requests.get(f"{API}/commissions/flip/artists", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_2fa_basics_setup_enable_disable(self):
        email, pw, tok, uid = register_throwaway("buyer", tag="reg2fa")
        r = requests.post(f"{API}/auth/2fa/setup", json={"method": "totp"}, headers=hdr(tok), timeout=15)
        assert r.status_code == 200
        secret = r.json()["secret"]
        totp = pyotp.TOTP(secret)
        r2 = requests.post(f"{API}/auth/2fa/enable", json={"code": totp.now()}, headers=hdr(tok), timeout=15)
        assert r2.status_code == 200
        assert r2.json()["enabled"] is True
        # disable
        time.sleep(1)
        rd = requests.post(f"{API}/auth/2fa/disable", json={"password": pw, "code": totp.now()}, headers=hdr(tok), timeout=15)
        assert rd.status_code == 200
