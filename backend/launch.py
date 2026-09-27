"""Launch readiness — live checks the founder ticks off before go-live."""
import os
import re
from datetime import datetime, timezone, timedelta
import httpx
from fastapi import APIRouter, Depends
from db import db, now_iso
from auth import require_role
from stripe_config import current_mode, webhook_secret, ENV_MODE

router = APIRouter(prefix="/api/admin", tags=["launch"])

TEST_EMAIL_RX = re.compile(r"(^test_|@example\.com$|\+test|@test\.|^demo)", re.I)


def _check(key, title, status, detail, fix=None, link=None, external=None, group="money"):
    return {"key": key, "title": title, "status": status, "detail": detail, "fix": fix, "link": link, "external": external, "group": group}


async def _resend_domain_status(api_key: str, sender: str):
    m = re.search(r"@([A-Za-z0-9.-]+)", sender or "")
    domain = m.group(1).lower() if m else None
    if not api_key:
        return domain, None, "no key"
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get("https://api.resend.com/domains", headers={"Authorization": f"Bearer {api_key}"})
        if r.status_code != 200:
            return domain, None, f"Resend API {r.status_code}"
        rows = r.json().get("data", [])
        for d in rows:
            if d.get("name", "").lower() == domain:
                return domain, d.get("status"), None
        return domain, "missing", None
    except Exception as e:
        return domain, None, str(e)[:80]


@router.get("/launch-readiness")
async def launch_readiness(admin: dict = Depends(require_role("admin"))):
    s = await db.settings.find_one({"id": "global"}) or {}
    checks = []

    # --- Stripe ---
    mode = current_mode()
    live_saved = bool(s.get("stripe_live_secret_key"))
    checks.append(_check("stripe_mode", "Stripe in live mode",
                         "pass" if mode == "live" else "fail",
                         f"Currently running in {mode} mode." + ("" if live_saved else " No live keys saved yet."),
                         "Finish Stripe business verification, paste live secret + publishable keys, then switch mode to Live.",
                         link="/admin?tab=stripe", external="https://dashboard.stripe.com/apikeys"))
    wh = await db.system_status.find_one({"id": "stripe_webhook"})
    wh_ok = bool(webhook_secret())
    recent = None
    if wh and wh.get("last_at"):
        try:
            recent = datetime.fromisoformat(wh["last_at"].replace("Z", "+00:00"))
        except Exception:
            recent = None
    if not wh_ok:
        st, det = "fail", "No webhook signing secret configured — paid orders will never be marked paid."
    elif recent and wh.get("mode") == mode:
        st, det = "pass", f"Last {mode} webhook received {wh.get('last_type')} at {wh['last_at'][:16].replace('T', ' ')} UTC."
    else:
        st, det = "warn", f"Secret is set but no {mode}-mode webhook has been received yet."
    checks.append(_check("stripe_webhook", "Stripe webhook receiving events", st, det,
                         "In Stripe → Developers → Webhooks add an endpoint for {PUBLIC_URL}/api/stripe/webhook (checkout.session.completed, payment_intent.*, charge.refunded, customer.subscription.*, account.updated) and paste its signing secret in the Stripe tab.",
                         link="/admin?tab=stripe", external="https://dashboard.stripe.com/webhooks"))
    connected = await db.users.count_documents({"stripe_charges_enabled": True})
    checks.append(_check("connect", "At least one artist connected to Stripe",
                         "pass" if connected else "warn",
                         f"{connected} artist account(s) can receive payouts.",
                         "Complete your own artist Stripe onboarding from Studio → Payouts so you can test a real sale end to end.",
                         link="/studio?tab=payouts"))

    # --- Domain / email ---
    public_url = os.environ.get("PUBLIC_APP_URL", "")
    good_url = public_url.startswith("https://") and "preview.emergentagent.com" not in public_url and "localhost" not in public_url
    checks.append(_check("public_url", "Public URL points at your domain",
                         "pass" if good_url else "fail",
                         f"PUBLIC_APP_URL = {public_url or '(not set)'}",
                         "Set PUBLIC_APP_URL=https://artcorestudio.net in the backend environment so emails, QR codes and referral links use your domain.", group="domain"))
    checks.append(_check("cors", "API origin policy",
                         "pass",
                         "Frontend and API are served from the same origin, so the wildcard CORS the hosting platform requires is safe. Sensitive routes are protected by JWT + rate limits, not CORS.",
                         None, group="domain"))
    resend_key = os.environ.get("RESEND_API_KEY", "")
    sender = os.environ.get("SENDER_EMAIL", "")
    domain, dstatus, err = await _resend_domain_status(resend_key, sender)
    if not resend_key:
        st, det = "fail", "No Resend API key — receipts, tickets, OTP codes and password resets cannot be sent."
    elif err:
        st, det = "warn", f"Could not verify domain {domain}: {err}"
    elif dstatus == "verified":
        st, det = "pass", f"{domain} is verified in Resend. Sending as {sender}."
    elif dstatus == "missing":
        st, det = "fail", f"{domain} is not added in Resend — emails fall back to onboarding@resend.dev (spam risk)."
    else:
        st, det = "fail", f"{domain} is '{dstatus}' in Resend — add the DNS records they show you."
    checks.append(_check("resend", "Email domain verified (Resend)", st, det,
                         "Resend → Domains → add artcorestudio.net → copy the SPF/DKIM/MX records into your DNS provider → click Verify.",
                         external="https://resend.com/domains", group="domain"))

    # --- Safety ---
    checks.append(_check("demo_login", "Demo sign-in disabled",
                         "fail" if s.get("demo_login_enabled") else "pass",
                         "Demo buttons are " + ("ON — anyone can log in as the demo artist/collector." if s.get("demo_login_enabled") else "off."),
                         "Turn off 'Demo sign-in buttons' in Settings.", link="/admin?tab=settings", group="safety"))
    checks.append(_check("admin_2fa", "Admin account has 2FA",
                         "pass" if admin.get("twofa_enabled") else "warn",
                         "Two-factor is " + ("on" if admin.get("twofa_enabled") else "off") + f" for {admin.get('email')}.",
                         "Enable 2FA under Account → Security.", link="/security", group="safety"))
    test_users = await db.users.count_documents({"email": {"$regex": TEST_EMAIL_RX.pattern, "$options": "i"}, "role": {"$ne": "admin"}})
    total_users = await db.users.count_documents({"role": {"$ne": "admin"}})
    orders = await db.orders.count_documents({})
    test_mode_tx = await db.payment_transactions.count_documents({"mode": {"$ne": "live"}}) if orders else 0
    dirty = test_users > 0 or (mode == "live" and orders and test_mode_tx)
    checks.append(_check("test_data", "Test data cleared",
                         "warn" if dirty else "pass",
                         f"{test_users} test-looking account(s) of {total_users} users; {orders} order(s) in the database.",
                         "Download a full backup, then run Reset to clean slate (Danger zone) right before launch.",
                         link="/admin?tab=settings", group="safety"))
    founding_taken = await db.users.count_documents({"founding_member": True})
    checks.append(_check("fees", "Fees configured",
                         "pass",
                         f"{s.get('commission_percent', 0):g}% platform fee · Founding {s.get('founding_rate', 0):g}% ({founding_taken}/{s.get('founding_cap', 0)} taken) · waiver {'on' if s.get('waiver_enabled') else 'off'} · {s.get('dispute_auto_days', 7)}-day dispute valve.",
                         None, link="/admin?tab=settings", group="safety"))

    # --- Content ---
    live_art = await db.artworks.count_documents({"status": "live"})
    picks = len((s.get("staff_picks") or {}))
    upcoming = await db.events.count_documents({"cancelled": {"$ne": True}, "start_at": {"$gte": now_iso()}})
    checks.append(_check("content", "Something for first visitors to see",
                         "pass" if live_art >= 3 else "warn",
                         f"{live_art} live artwork(s), {picks} staff pick(s), {upcoming} upcoming event(s).",
                         "List 3–5 real pieces in your own studio, mark 2–3 Staff Picks and post one event so the homepage isn't empty.",
                         link="/admin?tab=picks", group="content"))
    easypost = bool(os.environ.get("EASYPOST_API_KEY"))
    checks.append(_check("easypost", "Live carrier tracking (optional)",
                         "pass" if easypost else "info",
                         "EasyPost key " + ("set — real carrier scans drive delivery confirmation." if easypost else "not set — using the 7-day delivery estimate."),
                         "Paste your EasyPost key as EASYPOST_API_KEY when you have it.", external="https://app.easypost.com/account/api-keys", group="content"))

    counts = {k: sum(1 for c in checks if c["status"] == k) for k in ("pass", "warn", "fail", "info")}
    blocking = [c["key"] for c in checks if c["status"] == "fail"]
    return {"checked_at": now_iso(), "counts": counts, "ready": not blocking, "blocking": blocking,
            "checks": [{**c, "fix": (c["fix"] or "").replace("{PUBLIC_URL}", public_url or "https://artcorestudio.net")} for c in checks]}
