"""Iteration 23: Founding-artist rate-lock — settings, register, effective rate, admin grant/revoke/backfill, cap/enable flip."""
import os
import sys
sys.path.insert(0, "/app/backend")
import asyncio
import uuid
import pytest
import requests
from pathlib import Path

for envf in ["/app/backend/.env", "/app/frontend/.env"]:
    p = Path(envf)
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("monster@houseofmonster.com", os.environ["ADMIN_PASSWORD"])
ARTIST = ("demo.artist@artcorestudio.net", "DemoArtist2026!")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def _register(role="artist", tag="iter23"):
    email = f"TEST_{tag}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Passw0rd!123"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": f"Test {role}", "role": role}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    return email, pw, d["token"], d["user"]["id"]


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def artist_tok():
    return _login(*ARTIST)


@pytest.fixture(scope="module", autouse=True)
def restore_settings(admin_tok):
    """Ensure clean state at end regardless of test outcomes."""
    yield
    requests.patch(f"{API}/admin/settings",
                   json={"commission_percent": 4, "founding_enabled": True, "founding_rate": 4, "founding_cap": 500,
                         "waiver_days": 30, "waiver_max_sales": 5, "waiver_enabled": True},
                   headers=_hdr(admin_tok), timeout=20)


class TestSettingsExposesFounding:
    def test_settings_includes_founding_fields(self):
        r = requests.get(f"{API}/settings", timeout=15)
        assert r.status_code == 200
        s = r.json()
        assert s.get("founding_enabled") is True
        assert float(s.get("founding_rate")) == 4.0
        assert int(s.get("founding_cap")) == 500
        assert s.get("founding_taken") is not None and int(s["founding_taken"]) >= 35
        assert int(s["founding_left"]) == int(s["founding_cap"]) - int(s["founding_taken"])


class TestRegisterFounding:
    def test_new_artist_becomes_founding(self):
        # baseline taken
        s0 = requests.get(f"{API}/settings", timeout=15).json()
        taken0 = int(s0["founding_taken"])

        _, _, tok, uid = _register("artist")
        r = requests.get(f"{API}/waiver/me", headers=_hdr(tok), timeout=15)
        assert r.status_code == 200
        w = r.json()
        assert w["founding_member"] is True
        assert int(w["founding_number"]) == taken0 + 1
        assert float(w["locked_commission_percent"]) == 4.0
        # effective is 0 because 0% waiver window is active
        assert float(w["effective_commission_percent"]) == 0.0
        assert float(w["standard_commission_percent"]) == 4.0

    def test_new_buyer_not_founding(self):
        _, _, tok, _uid = _register("buyer")
        r = requests.get(f"{API}/waiver/me", headers=_hdr(tok), timeout=15)
        assert r.status_code == 200
        assert r.json().get("founding_member") in (False, None)


class TestCoreLock:
    """Core: locked min(global) applies, and 0% waiver overrides. Demo artist has no active waiver."""

    def test_demo_artist_locked_rate(self, admin_tok, artist_tok):
        # Bump global to 8%
        r = requests.patch(f"{API}/admin/settings", json={"commission_percent": 8}, headers=_hdr(admin_tok), timeout=20)
        assert r.status_code == 200, r.text

        try:
            # (a) demo artist auth'd → locked 4
            r = requests.get(f"{API}/settings/fee-preview?gross=100", headers=_hdr(artist_tok), timeout=15)
            assert r.status_code == 200
            d = r.json()
            assert float(d["commission_percent"]) == 4.0, d
            assert float(d["platform_take"]) == 4.0, d
            assert d["founding_locked"] is True

            # (b) unauthenticated → global 8
            r = requests.get(f"{API}/settings/fee-preview?gross=100", timeout=15)
            assert r.status_code == 200
            d = r.json()
            assert float(d["commission_percent"]) == 8.0
            assert float(d["platform_take"]) == 8.0

            # (c) unit-level settings_for_seller
            async def _check_unit():
                from db import db
                from waiver import settings_for_seller
                from payments import get_settings
                s = await get_settings()
                artist = await db.users.find_one({"email": ARTIST[0]})
                out = await settings_for_seller(artist["id"], s)
                assert float(out["commission_percent"]) == 4.0

                # Create a non-founding artist and verify 8.0
                new_email, _, _, new_uid = _register("artist")
                # Revoke founding & waiver
                r1 = requests.delete(f"{API}/admin/waiver/founding/{new_uid}", headers=_hdr(admin_tok), timeout=15)
                assert r1.status_code == 200
                r2 = requests.delete(f"{API}/admin/waiver/{new_uid}", headers=_hdr(admin_tok), timeout=15)
                assert r2.status_code == 200
                out2 = await settings_for_seller(new_uid, s)
                assert float(out2["commission_percent"]) == 8.0
                return new_uid

            new_uid = asyncio.get_event_loop().run_until_complete(_check_unit())
            assert new_uid

        finally:
            requests.patch(f"{API}/admin/settings", json={"commission_percent": 4}, headers=_hdr(admin_tok), timeout=20)

        # Restored: demo artist fee-preview → 4
        r = requests.get(f"{API}/settings/fee-preview?gross=100", headers=_hdr(artist_tok), timeout=15)
        assert float(r.json()["commission_percent"]) == 4.0

    def test_lower_global_wins(self, admin_tok, artist_tok):
        # global = 3 → founding artist gets min(4, 3) = 3
        r = requests.patch(f"{API}/admin/settings", json={"commission_percent": 3}, headers=_hdr(admin_tok), timeout=20)
        assert r.status_code == 200
        try:
            d = requests.get(f"{API}/settings/fee-preview?gross=100", headers=_hdr(artist_tok), timeout=15).json()
            assert float(d["commission_percent"]) == 3.0
        finally:
            requests.patch(f"{API}/admin/settings", json={"commission_percent": 4}, headers=_hdr(admin_tok), timeout=20)


class TestAdminEndpoints:
    def test_grant_already_founding(self, admin_tok):
        # demo artist is founding — grant returns 400
        async def _uid():
            from db import db
            u = await db.users.find_one({"email": ARTIST[0]})
            return u["id"]
        uid = asyncio.get_event_loop().run_until_complete(_uid())
        r = requests.post(f"{API}/admin/waiver/founding/{uid}", headers=_hdr(admin_tok), timeout=15)
        assert r.status_code == 400
        assert "Already a founding" in r.text or "already" in r.text.lower()

    def test_grant_fresh_then_revoke(self, admin_tok):
        # Create a fresh artist, revoke first (register auto-grants), then re-grant via admin
        _, _, _, uid = _register("artist", tag="freshgrant")
        # revoke via admin
        r = requests.delete(f"{API}/admin/waiver/founding/{uid}", headers=_hdr(admin_tok), timeout=15)
        assert r.status_code == 200
        # /waiver/me for this user should show founding_member false — login required, we'll query directly via user token isn't kept — use admin
        # Grant fresh
        r = requests.post(f"{API}/admin/waiver/founding/{uid}", headers=_hdr(admin_tok), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "founding_number" in data
        assert float(data["locked_commission_percent"]) == 4.0

    def test_backfill(self, admin_tok):
        r = requests.post(f"{API}/admin/waiver/founding/backfill", headers=_hdr(admin_tok), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "granted" in d
        assert int(d["granted"]) >= 0

    def test_non_admin_forbidden(self, artist_tok):
        r = requests.post(f"{API}/admin/waiver/founding/some-user-id", headers=_hdr(artist_tok), timeout=15)
        assert r.status_code == 403
        r = requests.post(f"{API}/admin/waiver/founding/backfill", headers=_hdr(artist_tok), timeout=15)
        assert r.status_code == 403


class TestCapAndEnable:
    def test_cap_blocks_new_founding(self, admin_tok):
        s = requests.get(f"{API}/settings", timeout=15).json()
        taken = int(s["founding_taken"])
        # set cap to current taken
        r = requests.patch(f"{API}/admin/settings", json={"founding_cap": taken}, headers=_hdr(admin_tok), timeout=15)
        assert r.status_code == 200
        try:
            _, _, tok, _uid = _register("artist", tag="capblock")
            w = requests.get(f"{API}/waiver/me", headers=_hdr(tok), timeout=15).json()
            assert w.get("founding_member") in (False, None)
        finally:
            requests.patch(f"{API}/admin/settings", json={"founding_cap": 500}, headers=_hdr(admin_tok), timeout=15)

    def test_disabled_blocks_new_founding(self, admin_tok):
        r = requests.patch(f"{API}/admin/settings", json={"founding_enabled": False}, headers=_hdr(admin_tok), timeout=15)
        assert r.status_code == 200
        try:
            _, _, tok, _uid = _register("artist", tag="fdis")
            w = requests.get(f"{API}/waiver/me", headers=_hdr(tok), timeout=15).json()
            assert w.get("founding_member") in (False, None)
        finally:
            requests.patch(f"{API}/admin/settings", json={"founding_enabled": True}, headers=_hdr(admin_tok), timeout=15)


class TestRegression:
    def test_unauth_fee_preview_net(self):
        r = requests.get(f"{API}/settings/fee-preview?gross=100", timeout=15)
        assert r.status_code == 200
        d = r.json()
        # commission 4 + processing 2.9% + 0.30 = 4 + 2.9 + 0.30 = 7.20 → net 92.80
        assert float(d["commission_percent"]) == 4.0
        assert abs(float(d["net"]) - 92.8) < 0.05, d
