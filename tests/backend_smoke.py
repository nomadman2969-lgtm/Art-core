"""House of Monster backend smoke test."""
import io
import sys
import time
import requests
from PIL import Image

BASE = "https://monster-curated.preview.emergentagent.com/api"
results = {"passed": [], "failed": []}


def check(name, cond, evidence=""):
    if cond:
        print(f"PASS: {name}")
        results["passed"].append(name)
    else:
        print(f"FAIL: {name} — {evidence}")
        results["failed"].append({"name": name, "evidence": str(evidence)[:400]})


def req(method, path, token=None, **kw):
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, f"{BASE}{path}", headers=headers, timeout=30, **kw)
    return r


# ---------- 1. Public root & settings ----------
r = req("GET", "/")
check("GET /api/ root", r.status_code == 200 and r.json().get("status") == "ok", r.text)

r = req("GET", "/settings")
check("GET /api/settings has fields",
      r.status_code == 200 and "commission_percent" in r.json() and "upload_fee" in r.json() and "currency" in r.json(), r.text)

# ---------- 2. Admin login ----------
r = req("POST", "/auth/login", json={"email": "monster@houseofmonster.com", "password": "MonsterAdmin2026!"})
check("Admin login", r.status_code == 200 and r.json()["user"]["role"] == "admin", r.text)
admin_token = r.json()["token"]

# ---------- 3. Register buyer + artist ----------
ts = int(time.time())
buyer_email = f"buyer_{ts}@test.com"
artist_email = f"artist_{ts}@test.com"

r = req("POST", "/auth/register", json={"email": buyer_email, "password": "Pass1234!", "name": "Buyer T", "role": "buyer"})
check("Register buyer", r.status_code == 200 and r.json()["user"]["role"] == "buyer", r.text)
buyer_token = r.json()["token"]

r = req("POST", "/auth/register", json={"email": artist_email, "password": "Pass1234!", "name": "Artist T", "role": "artist"})
check("Register artist", r.status_code == 200 and r.json()["user"]["role"] == "artist", r.text)
artist_token = r.json()["token"]
artist_id = r.json()["user"]["id"]

# ---------- 4. GET /auth/me ----------
r = req("GET", "/auth/me", token=buyer_token)
check("GET /auth/me buyer", r.status_code == 200 and r.json()["email"] == buyer_email, r.text)

# ---------- 5. PATCH /auth/me ----------
r = req("PATCH", "/auth/me", token=artist_token, json={"bio": "I make magenta"})
check("PATCH /auth/me updates bio", r.status_code == 200 and r.json().get("bio") == "I make magenta", r.text)

# ---------- 6. Admin settings PATCH ----------
r = req("PATCH", "/admin/settings", token=buyer_token, json={"upload_fee": 0})
check("PATCH /admin/settings non-admin gets 403", r.status_code == 403, f"{r.status_code} {r.text}")

r = req("PATCH", "/admin/settings", token=admin_token, json={"upload_fee": 0})
check("PATCH /admin/settings admin ok (fee=0)", r.status_code == 200, r.text)

# ---------- 7. Upload image ----------
img = Image.new("RGB", (200, 200), (200, 50, 100))
buf = io.BytesIO()
img.save(buf, format="JPEG")
buf.seek(0)
files = {"file": ("test.jpg", buf.getvalue(), "image/jpeg")}
r = req("POST", "/upload/image", token=artist_token, files=files)
check("POST /upload/image", r.status_code == 200 and "path" in r.json() and "url" in r.json(), r.text)
image_path = r.json()["path"] if r.status_code == 200 else None
image_url = r.json()["url"] if r.status_code == 200 else None

if image_path:
    # GET /api/files/{path}
    r2 = requests.get(f"{BASE}/files/{image_path}", timeout=30)
    check("GET /api/files/{path}", r2.status_code == 200 and r2.headers.get("content-type", "").startswith("image"), f"{r2.status_code} {r2.headers.get('content-type')}")

# ---------- 8. Artist creates artwork w/ fee=0 -> goes live immediately ----------
art_payload = {
    "title": "Magenta Dream",
    "description": "Test artwork",
    "price": 250.0,
    "medium": "painting",
    "images": [image_path or "dummy.jpg"],
    "dimensions": "24x36",
    "year": 2026,
}
r = req("POST", "/artworks", token=artist_token, json=art_payload)
check("POST /artworks with fee=0 -> live",
      r.status_code == 200 and r.json().get("status") == "live",
      f"{r.status_code} {r.text[:300]}")
art_id_live = r.json().get("id") if r.status_code == 200 else None

# ---------- 9. Role guard: buyer cannot POST /artworks ----------
r = req("POST", "/artworks", token=buyer_token, json=art_payload)
check("Buyer cannot POST /artworks (role guard)", r.status_code in (401, 403), f"{r.status_code} {r.text[:200]}")

# ---------- 10. Restore upload_fee=5, artist create -> pending_fee + Stripe checkout ----------
r = req("PATCH", "/admin/settings", token=admin_token, json={"upload_fee": 5.0})
check("Restore upload_fee=5", r.status_code == 200, r.text)

r = req("POST", "/artworks", token=artist_token, json=art_payload)
check("POST /artworks with fee>0 -> pending_fee",
      r.status_code == 200 and r.json().get("status") == "pending_fee",
      f"{r.status_code} {r.text[:300]}")
art_id_pending = r.json().get("id") if r.status_code == 200 else None

# ---------- 11. Upload fee Stripe checkout ----------
if art_id_pending:
    r = req("POST", "/payments/upload-fee", token=artist_token,
            json={"artwork_id": art_id_pending, "origin_url": "https://monster-curated.preview.emergentagent.com"})
    check("POST /payments/upload-fee returns checkout_url",
          r.status_code == 200 and "checkout_url" in r.json() and r.json()["checkout_url"].startswith("http"),
          f"{r.status_code} {r.text[:300]}")

# ---------- 12. Buyer checkout ----------
if art_id_live:
    r = req("POST", "/payments/checkout", token=buyer_token,
            json={"items": [{"artwork_id": art_id_live, "quantity": 1}],
                  "shipping": {"name": "Buyer T", "address_line1": "123 St", "city": "NY", "state": "NY", "postal_code": "10001", "country": "US"},
                  "origin_url": "https://monster-curated.preview.emergentagent.com"})
    check("POST /payments/checkout returns checkout_url",
          r.status_code == 200 and "checkout_url" in r.json(),
          f"{r.status_code} {r.text[:300]}")
    session_id = r.json().get("session_id") if r.status_code == 200 else None

    if session_id:
        r = req("GET", f"/payments/status/{session_id}", token=buyer_token)
        check("GET /payments/status/{sid} returns status",
              r.status_code == 200 and "status" in r.json(),
              f"{r.status_code} {r.text[:300]}")

# fake session id -> 404
r = req("GET", "/payments/status/cs_test_fake_nonexistent_12345", token=buyer_token)
check("Fake session id -> 404", r.status_code == 404, f"{r.status_code} {r.text[:200]}")

# ---------- 13. Artworks gallery + filters ----------
r = req("GET", "/artworks", params={"medium": "painting", "max_price": 1000, "sort": "price_asc"})
check("GET /artworks with filters", r.status_code == 200 and isinstance(r.json(), list), r.text[:200])

if art_id_live:
    r = req("GET", f"/artworks/{art_id_live}")
    check("GET /artworks/{id} with artist enrichment",
          r.status_code == 200 and r.json().get("id") == art_id_live and "artist" in r.json(),
          f"{r.status_code} {r.text[:300]}")

# ---------- 14. AOTW ----------
r = req("GET", "/artworks/aotw")
# might be null or a prior AOTW; accept 200 with json
check("GET /artworks/aotw responds 200", r.status_code == 200, r.text[:200])

if art_id_live:
    r = req("POST", f"/artworks/{art_id_live}/submit-aotw", token=artist_token)
    check("Artist submit AOTW", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    r = req("GET", "/admin/aotw/submissions", token=admin_token)
    check("Admin list AOTW submissions", r.status_code == 200 and isinstance(r.json(), list), f"{r.status_code} {r.text[:200]}")

    r = req("POST", "/admin/aotw", token=admin_token, json={"artwork_id": art_id_live})
    check("Admin set AOTW", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    r = req("GET", "/artworks/aotw")
    check("GET /artworks/aotw returns set artwork",
          r.status_code == 200 and r.json() and r.json().get("id") == art_id_live,
          f"{r.status_code} {r.text[:300]}")

    r = req("POST", "/admin/featured", token=admin_token, json={"artwork_id": art_id_live, "featured": True})
    check("Admin toggle featured", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

# ---------- 15. Admin stats / mentorship / newsletter ----------
r = req("GET", "/admin/stats", token=admin_token)
check("GET /admin/stats", r.status_code == 200 and isinstance(r.json(), dict), r.text[:200])

r = req("POST", "/admin/mentorship", token=admin_token,
        json={"user_email": artist_email, "reason": "Great work"})
check("POST /admin/mentorship flag", r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}")
ment_id = None
if r.status_code in (200, 201):
    try:
        ment_id = r.json().get("id")
    except Exception:
        pass

if ment_id:
    r = req("PATCH", f"/admin/mentorship/{ment_id}", token=admin_token, json={"resolved": True})
    check("PATCH /admin/mentorship resolve", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

r = req("POST", "/newsletter", json={"email": f"news_{ts}@test.com"})
check("POST /newsletter signup public", r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}")

# ---------- 16. Artist dashboard + connect ----------
r = req("GET", "/artist/dashboard", token=artist_token)
check("GET /artist/dashboard", r.status_code == 200 and isinstance(r.json(), dict), r.text[:200])

r = req("POST", "/artist/connect/start", token=artist_token)
check("POST /artist/connect/start returns onboarding_url",
      r.status_code == 200 and "onboarding_url" in r.json(),
      f"{r.status_code} {r.text[:300]}")

r = req("POST", "/artist/connect/complete", token=artist_token)
check("POST /artist/connect/complete -> connected", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

# ---------- 17. Role guard: artist cannot access /admin/* ----------
r = req("GET", "/admin/stats", token=artist_token)
check("Artist cannot access /admin/stats (403)", r.status_code == 403, f"{r.status_code} {r.text[:200]}")

# ---------- summary ----------
total = len(results["passed"]) + len(results["failed"])
print(f"\n\n===== SUMMARY: {len(results['passed'])}/{total} passed =====")
for f in results["failed"]:
    print(f"  FAIL: {f['name']} — {f['evidence'][:200]}")

sys.exit(0 if not results["failed"] else 1)
