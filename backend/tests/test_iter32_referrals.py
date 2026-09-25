"""Artist referral rewards — iteration 32."""
import os
import time
import uuid
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://monster-curated.preview.emergentagent.com"
API = f"{BASE}/api"
ADMIN_EMAIL = "admin@artcorestudio.net"
ADMIN_PW = "atg-6+XxIRZe1zLUDCcwB!_a"

TAG = uuid.uuid4().hex[:6]


def _reg(role, tag):
    payload = {"email": f"ref_{TAG}_{tag}@example.com", "password": "RefTest123!",
               "name": f"Ref {tag.upper()}", "role": role}
    return payload


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def artist_A():
    p = _reg("artist", "a")
    r = requests.post(f"{API}/auth/register", json=p)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"tok": d["token"], "id": d["user"]["id"], "email": p["email"], "name": p["name"]}


def test_01_referrals_me_shape(artist_A):
    r = requests.get(f"{API}/referrals/me", headers=hdr(artist_A["tok"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["code"]) == 6
    assert not any(c in d["code"] for c in "OI01"), f"code has forbidden char: {d['code']}"
    assert f"ref={d['code']}" in d["link"]
    assert d["invited"] == 0 and d["converted"] == 0
    artist_A["code"] = d["code"]


def test_02_check_code_valid_and_case_insensitive(artist_A):
    code = artist_A["code"]
    r = requests.get(f"{API}/referrals/check/{code}")
    assert r.status_code == 200
    assert r.json()["valid"] is True
    assert r.json()["referrer_name"] == artist_A["name"]
    r2 = requests.get(f"{API}/referrals/check/{code.lower()}")
    assert r2.status_code == 200
    assert r2.json()["valid"] is True


def test_03_check_bogus_404():
    r = requests.get(f"{API}/referrals/check/BOGUS0")
    assert r.status_code == 404


def test_04_register_artist_B_with_code_lowercase(artist_A):
    p = _reg("artist", "b")
    p["referral_code"] = artist_A["code"].lower()
    r = requests.post(f"{API}/auth/register", json=p)
    assert r.status_code == 200, r.text
    d = r.json()
    artist_A["B_id"] = d["user"]["id"]
    artist_A["B_tok"] = d["token"]
    artist_A["B_name"] = p["name"]
    artist_A["B_email"] = p["email"]

    # A /me should show 1 invited
    r2 = requests.get(f"{API}/referrals/me", headers=hdr(artist_A["tok"]))
    d2 = r2.json()
    assert d2["invited"] == 1, d2
    assert d2["converted"] == 0
    assert d2["invitees"][0]["name"] == p["name"]


def test_05_A_has_referral_joined_notification(artist_A):
    r = requests.get(f"{API}/notifications", headers=hdr(artist_A["tok"]))
    assert r.status_code == 200
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", [])
    kinds = [n.get("kind") for n in items]
    assert "referral_joined" in kinds, kinds


def test_06_buyer_with_code_ignored(artist_A):
    p = _reg("buyer", "c")
    p["referral_code"] = artist_A["code"]
    r = requests.post(f"{API}/auth/register", json=p)
    assert r.status_code == 200
    r2 = requests.get(f"{API}/referrals/me", headers=hdr(artist_A["tok"]))
    assert r2.json()["invited"] == 1, "buyer must not count"

    # buyer forbidden from /me
    buyer_tok = r.json()["token"]
    r3 = requests.get(f"{API}/referrals/me", headers=hdr(buyer_tok))
    assert r3.status_code == 403


def test_07_first_sale_conversion(artist_A):
    """Directly invoke waiver.after_sale twice for B; ensure credit increments once."""
    import subprocess
    B_id = artist_A["B_id"]
    A_id = artist_A["id"]
    script = f"""
import asyncio, sys
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
async def main():
    from waiver import after_sale, effective_rate
    from payments import get_settings
    from db import db
    settings = await get_settings()
    B = await db.users.find_one({{"id": "{B_id}"}})
    eff = effective_rate(B, settings)
    await after_sale("{B_id}", eff)
    B = await db.users.find_one({{"id": "{B_id}"}})
    eff = effective_rate(B, settings)
    await after_sale("{B_id}", eff)
    A = await db.users.find_one({{"id": "{A_id}"}})
    print("A_fee_free_sales:", A.get("fee_free_sales"))
    print("A_referral_conversions:", A.get("referral_conversions"))
    print("B_converted_at:", B.get("referral_converted_at"))
asyncio.run(main())
"""
    p = subprocess.run(["python", "-c", script], capture_output=True, text=True, cwd="/app/backend")
    print("STDOUT:", p.stdout)
    print("STDERR:", p.stderr)
    assert "A_fee_free_sales: 1" in p.stdout, p.stdout + p.stderr
    assert "A_referral_conversions: 1" in p.stdout
    assert "B_converted_at:" in p.stdout and "None" not in p.stdout.split("B_converted_at:")[1].splitlines()[0]


def test_08_badges(artist_A):
    r = requests.get(f"{API}/users/{artist_A['id']}/badges")
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("badges", [])
    badges = {b["id"]: b for b in items}
    assert badges.get("recruiter", {}).get("earned"), badges
    rb = requests.get(f"{API}/users/{artist_A['B_id']}/badges").json()
    items_b = rb if isinstance(rb, list) else rb.get("badges", [])
    b_map = {b["id"]: b for b in items_b}
    assert b_map.get("crew", {}).get("earned"), b_map


def test_09_reward_and_badge_notifications(artist_A):
    r = requests.get(f"{API}/notifications", headers=hdr(artist_A["tok"]))
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", [])
    kinds = [n.get("kind") for n in items]
    assert "referral_reward" in kinds

    r2 = requests.get(f"{API}/notifications", headers=hdr(artist_A["B_tok"]))
    body2 = r2.json()
    items2 = body2 if isinstance(body2, list) else body2.get("items", [])
    kinds2 = [n.get("kind") for n in items2]
    assert "referral_badge" in kinds2


def test_10_expire_A_waiver_consume_credit(artist_A):
    """Expire A's waiver → effective_rate returns 0% via fee_free_referral; after_sale consumes the credit and next rate returns to founding 4%."""
    import subprocess
    A_id = artist_A["id"]
    script = f"""
import asyncio, sys
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
async def main():
    from waiver import after_sale, effective_rate
    from payments import get_settings
    from db import db
    await db.users.update_one({{"id": "{A_id}"}}, {{"$set": {{"fee_waiver_until": "2020-01-01T00:00:00+00:00"}}}})
    settings = await get_settings()
    A = await db.users.find_one({{"id": "{A_id}"}})
    eff = effective_rate(A, settings)
    print("pre_rate:", eff["commission_percent"], "fee_free_referral:", eff.get("fee_free_referral"))
    await after_sale("{A_id}", eff)
    A2 = await db.users.find_one({{"id": "{A_id}"}})
    print("A_fee_free_sales:", A2.get("fee_free_sales"))
    print("A_fee_free_used:", A2.get("fee_free_used"))
    eff2 = effective_rate(A2, settings)
    print("post_rate:", eff2["commission_percent"])
asyncio.run(main())
"""
    p = subprocess.run(["python", "-c", script], capture_output=True, text=True, cwd="/app/backend")
    print("STDOUT:", p.stdout, "STDERR:", p.stderr)
    assert "pre_rate: 0.0 fee_free_referral: True" in p.stdout, p.stdout
    assert "A_fee_free_sales: 0" in p.stdout
    assert "A_fee_free_used: 1" in p.stdout
    assert "post_rate: 4.0" in p.stdout


def test_11_regression_fee_preview_no_waiver_no_credit():
    """A fresh seller with no waiver and no credit should get founding 4% (they enroll at signup) OR standard 12% if founding disabled."""
    # Create fresh artist without a code
    p = _reg("artist", "reg")
    p["email"] = f"ref_{TAG}_reg@example.com"
    r = requests.post(f"{API}/auth/register", json=p)
    assert r.status_code == 200
    tok = r.json()["token"]
    # /waiver/me shows effective vs standard
    rw = requests.get(f"{API}/waiver/me", headers=hdr(tok))
    assert rw.status_code == 200
    d = rw.json()
    # Fresh signup has 30-day waiver → active True, effective 0%; that's expected
    # But standard rate must still be either 4 (founding lock) or 12
    assert d["standard_commission_percent"] in (4.0, 12.0), d


def test_12_cleanup_admin_reset(admin_tok):
    r = requests.post(f"{API}/admin/reset-to-clean-slate",
                      json={"confirm": "DELETE EVERYTHING"}, headers=hdr(admin_tok))
    assert r.status_code == 200, r.text
    s = requests.get(f"{API}/settings").json()
    assert s.get("founding_taken", 0) == 0, s
