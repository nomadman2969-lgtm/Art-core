"""Tests for Studio Starter Templates and Admin Refund Console (iteration 8)."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "monster@houseofmonster.com"
ADMIN_PW = "MonsterAdmin2026!"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("token")


@pytest.fixture(scope="module")
def admin_token():
    tok = _login(ADMIN_EMAIL, ADMIN_PW)
    if not tok:
        pytest.skip("Admin login failed")
    return tok


@pytest.fixture(scope="module")
def admin_hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def buyer_token():
    email = f"TEST_buyer_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "TestPass123!", "name": "Test Buyer", "role": "buyer"
    }, timeout=15)
    if r.status_code not in (200, 201):
        pytest.skip(f"Register failed: {r.status_code} {r.text[:200]}")
    return r.json().get("token")


# ---------- Studio Templates ----------
class TestStudioTemplates:
    def test_list_templates(self):
        r = requests.get(f"{API}/studio/templates", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        ids = {t["id"] for t in data}
        assert {"emerging_artist", "gallery_owner", "print_shop", "dark_solo"}.issubset(ids)
        for t in data:
            for k in ("id", "name", "description", "vibe", "theme", "accent"):
                assert k in t, f"missing {k} in {t}"

    def test_apply_unknown_template(self, admin_hdr):
        r = requests.post(f"{API}/studio/apply-template",
                          json={"template_id": "not_a_template"}, headers=admin_hdr, timeout=15)
        assert r.status_code == 404

    def test_apply_print_shop_then_publish(self, admin_hdr):
        # Apply
        r = requests.post(f"{API}/studio/apply-template",
                          json={"template_id": "print_shop"}, headers=admin_hdr, timeout=15)
        assert r.status_code == 200, r.text
        cfg = r.json()
        draft = cfg.get("draft") or {}
        assert draft, "expected a draft to be present"
        assert draft.get("theme") == "neon_digital"
        secs = draft.get("sections") or []
        assert len(secs) == 6, f"expected 6 sections, got {len(secs)}"
        # IDs should be regenerated (not the t-* placeholders)
        for s in secs:
            assert not s["id"].startswith("t-"), f"template placeholder ID leaked: {s['id']}"
        assert draft.get("commission_open") is True
        assert draft.get("commission_blurb")

        # Publish
        pr = requests.post(f"{API}/studio/publish", headers=admin_hdr, timeout=15)
        assert pr.status_code == 200, pr.text
        live = pr.json()
        assert live.get("theme") == "neon_digital"
        assert len(live.get("sections") or []) == 6
        # draft should be cleared
        assert not live.get("draft")

    def test_apply_requires_auth(self):
        r = requests.post(f"{API}/studio/apply-template",
                          json={"template_id": "print_shop"}, timeout=15)
        assert r.status_code in (401, 403)


# ---------- Refund Console ----------
class TestRefundConsole:
    def test_refundable_requires_admin(self, buyer_token):
        r = requests.get(f"{API}/admin/refundable",
                         headers={"Authorization": f"Bearer {buyer_token}"}, timeout=15)
        assert r.status_code == 403

    def test_refundable_unauth(self):
        r = requests.get(f"{API}/admin/refundable", timeout=15)
        assert r.status_code in (401, 403)

    def test_refundable_admin_ok(self, admin_hdr):
        r = requests.get(f"{API}/admin/refundable", headers=admin_hdr, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Expected list or dict wrapping a list
        items = data if isinstance(data, list) else (data.get("items") or data.get("refundable") or [])
        assert isinstance(items, list)
        for it in items[:5]:
            for k in ("kind", "id", "amount"):
                assert k in it, f"missing {k} in refundable item {it}"
            assert it["kind"] in ("order", "commission")

    def test_refund_unknown_order_404(self, admin_hdr):
        r = requests.post(f"{API}/admin/orders/does-not-exist/refund",
                          json={"reason": "requested_by_customer"}, headers=admin_hdr, timeout=15)
        assert r.status_code == 404

    def test_refund_unknown_commission_404(self, admin_hdr):
        r = requests.post(f"{API}/admin/commissions/does-not-exist/refund",
                          json={"reason": "requested_by_customer"}, headers=admin_hdr, timeout=15)
        assert r.status_code == 404

    def test_refund_non_admin_forbidden(self, buyer_token):
        r = requests.post(f"{API}/admin/orders/anything/refund",
                          json={"reason": "requested_by_customer"},
                          headers={"Authorization": f"Bearer {buyer_token}"}, timeout=15)
        assert r.status_code == 403
