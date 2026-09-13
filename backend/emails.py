"""Transactional email helper (Resend).

Non-blocking send_email() falls back gracefully:
- If RESEND_API_KEY is missing → logs and returns False (never crashes callers)
- If custom domain (`refunds@artcorestudio.net`) is not yet DNS-verified → retries with sandbox sender
"""
import asyncio
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

_INITIALIZED = False


def _init():
    global _INITIALIZED
    if _INITIALIZED:
        return True
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return False
    try:
        import resend
        resend.api_key = api_key
        _INITIALIZED = True
        return True
    except Exception as e:  # noqa
        log.warning("resend init failed: %s", e)
        return False


async def send_email(to: str, subject: str, html: str, from_addr: Optional[str] = None) -> bool:
    if not _init():
        log.info("send_email skipped (no RESEND_API_KEY): to=%s subject=%s", to, subject)
        return False
    import resend as _resend
    primary = from_addr or os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev"
    fallback = os.environ.get("SENDER_FALLBACK") or "onboarding@resend.dev"

    def _try(sender: str):
        return _resend.Emails.send({
            "from": sender,
            "to": [to],
            "subject": subject,
            "html": html,
        })

    try:
        result = await asyncio.to_thread(_try, primary)
        return bool(result.get("id"))
    except Exception as e:
        msg = str(e)
        # Common Resend failure when domain isn't verified: fall back to sandbox
        if "domain" in msg.lower() or "not verified" in msg.lower() or "403" in msg:
            log.info("Primary sender %s failed (%s) — trying fallback %s", primary, msg, fallback)
            try:
                result = await asyncio.to_thread(_try, fallback)
                return bool(result.get("id"))
            except Exception as e2:
                log.warning("Fallback send failed: %s", e2)
                return False
        log.warning("send_email failed: %s", e)
        return False


# ----- Email templates -----

def _wrap(body: str, title: str = "Art Core") -> str:
    return f"""
<!doctype html>
<html><body style="margin:0;padding:0;background:#0A0A0C;font-family:Helvetica,Arial,sans-serif;color:#e5e7eb">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0A0A0C;padding:24px">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0"
        style="background:#121214;border:1px solid rgba(255,255,255,0.08);border-radius:6px;overflow:hidden">
        <tr><td style="padding:24px 28px;border-bottom:1px solid rgba(255,255,255,0.08)">
          <div style="font-family:Impact,Arial Black,sans-serif;letter-spacing:1px;font-size:28px;color:#fff">
            ART <span style="color:#CCFF00">CORE</span>
          </div>
          <div style="font-size:11px;color:#71717a;letter-spacing:2px;text-transform:uppercase;margin-top:6px">
            {title}
          </div>
        </td></tr>
        <tr><td style="padding:28px;color:#e5e7eb;font-size:14px;line-height:1.6">
          {body}
        </td></tr>
        <tr><td style="padding:16px 28px;border-top:1px solid rgba(255,255,255,0.08);
          font-size:11px;color:#71717a;text-align:center">
          Art Core — the social marketplace for visual artists.<br>
          <a href="https://artcorestudio.net" style="color:#CCFF00;text-decoration:none">artcorestudio.net</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""


def refund_email_html(user_name: str, event_title: str, amount: float, event_when: str) -> str:
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  Refund on the way
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:24px">
  Hey {user_name}, the host cancelled <strong style="color:#fff">{event_title}</strong>.
  We've reversed the charge back to your original payment method.
</div>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="background:rgba(204,255,0,0.08);border:1px solid rgba(204,255,0,0.3);border-radius:4px;margin-bottom:24px">
  <tr><td style="padding:20px">
    <div style="font-size:11px;color:#CCFF00;letter-spacing:2px;text-transform:uppercase">Refund amount</div>
    <div style="font-family:Impact,Arial Black,sans-serif;font-size:44px;color:#CCFF00;margin-top:6px">
      ${amount:,.2f}
    </div>
    <div style="font-size:12px;color:#a1a1aa;margin-top:8px">
      Refund typically lands within 5–10 business days depending on your bank.
    </div>
  </td></tr>
</table>

<div style="font-size:12px;color:#71717a">
  Event was scheduled for: <strong style="color:#e5e7eb">{event_when}</strong>
</div>

<div style="margin-top:28px">
  <a href="https://artcorestudio.net/events" style="display:inline-block;background:#CCFF00;color:#000;
     padding:12px 22px;text-decoration:none;font-family:Impact,Arial Black,sans-serif;
     letter-spacing:1px;text-transform:uppercase;font-size:13px;border-radius:2px">
    Find another event →
  </a>
</div>
"""
    return _wrap(body, "Refund Notice")


def ticket_receipt_html(user_name: str, event_title: str, amount: float, event_when: str, event_where: str) -> str:
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  You're going
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:24px">
  Hey {user_name}, your ticket to <strong style="color:#fff">{event_title}</strong> is confirmed.
</div>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.3);border-radius:4px;margin-bottom:24px">
  <tr><td style="padding:20px">
    <div style="font-size:11px;color:#7C3AED;letter-spacing:2px;text-transform:uppercase">Ticket</div>
    <div style="font-family:Impact,Arial Black,sans-serif;font-size:24px;color:#fff;margin-top:6px">{event_title}</div>
    <div style="font-size:12px;color:#a1a1aa;margin-top:10px">📅 {event_when}</div>
    <div style="font-size:12px;color:#a1a1aa">📍 {event_where}</div>
    <div style="font-size:12px;color:#CCFF00;margin-top:10px">Paid: ${amount:,.2f}</div>
  </td></tr>
</table>

<div style="font-size:12px;color:#71717a">
  Open the app on your phone to show the QR code at the door.
</div>

<div style="margin-top:28px">
  <a href="https://artcorestudio.net/tickets" style="display:inline-block;background:#CCFF00;color:#000;
     padding:12px 22px;text-decoration:none;font-family:Impact,Arial Black,sans-serif;
     letter-spacing:1px;text-transform:uppercase;font-size:13px;border-radius:2px">
    Open your ticket →
  </a>
</div>
"""
    return _wrap(body, "Ticket Confirmation")


def _fmt_when(iso_str: str) -> str:
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat((iso_str or "").replace("Z", "+00:00")).strftime("%b %d, %Y · %-I:%M %p")
    except Exception:
        return iso_str or "TBA"


def waitlist_position_html(user_name: str, event: dict, position: int) -> str:
    where = ", ".join(x for x in [(event.get("location") or {}).get("address"), (event.get("location") or {}).get("city")] if x) or "TBA"
    ordinal = f"#{position}"
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  You're on the list
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:24px">
  Hey {user_name}, <strong style="color:#fff">{event['title']}</strong> is full right now — but you're queued.
  We'll email you the moment a seat opens.
</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="background:rgba(124,58,237,0.10);border:1px solid rgba(124,58,237,0.35);border-radius:4px;margin-bottom:24px">
  <tr><td style="padding:20px">
    <div style="font-size:11px;color:#a78bfa;letter-spacing:2px;text-transform:uppercase">Your waitlist position</div>
    <div style="font-family:Impact,Arial Black,sans-serif;font-size:56px;color:#fff;margin-top:6px;line-height:1">{ordinal}</div>
    <div style="font-size:12px;color:#a1a1aa;margin-top:10px">📅 {_fmt_when(event.get('start_at'))}</div>
    <div style="font-size:12px;color:#a1a1aa">📍 {where}</div>
  </td></tr>
</table>
<div style="font-size:12px;color:#71717a">
  Seats are offered in order. If the event is paid, you'll get a 15-minute checkout hold when it's your turn.
</div>
<div style="margin-top:28px">
  <a href="https://artcorestudio.net/events/{event['id']}" style="display:inline-block;background:#CCFF00;color:#000;
     padding:12px 22px;text-decoration:none;font-family:Impact,Arial Black,sans-serif;
     letter-spacing:1px;text-transform:uppercase;font-size:13px;border-radius:2px">
    View event →
  </a>
</div>
"""
    return _wrap(body, "Waitlist Confirmation")


def event_broadcast_html(user_name: str, host_name: str, event: dict, subject: str, message: str) -> str:
    import html as _h
    where = ", ".join(x for x in [(event.get("location") or {}).get("address"), (event.get("location") or {}).get("city")] if x) or "TBA"
    safe_msg = _h.escape(message).replace("\n", "<br>")
    body = f"""
<div style="font-size:11px;color:#CCFF00;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px">
  Update from {_h.escape(host_name)}
</div>
<div style="font-family:Impact,Arial Black,sans-serif;font-size:32px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  {_h.escape(subject)}
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:20px">
  Hey {_h.escape(user_name)} — a message about <strong style="color:#fff">{_h.escape(event['title'])}</strong>:
</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="background:rgba(255,255,255,0.04);border-left:3px solid #CCFF00;border-radius:2px;margin-bottom:24px">
  <tr><td style="padding:18px 20px;font-size:14px;color:#e5e7eb;line-height:1.7">{safe_msg}</td></tr>
</table>
<div style="font-size:12px;color:#a1a1aa">📅 {_fmt_when(event.get('start_at'))}</div>
<div style="font-size:12px;color:#a1a1aa">📍 {_h.escape(where)}</div>
<div style="margin-top:28px">
  <a href="https://artcorestudio.net/events/{event['id']}" style="display:inline-block;background:#CCFF00;color:#000;
     padding:12px 22px;text-decoration:none;font-family:Impact,Arial Black,sans-serif;
     letter-spacing:1px;text-transform:uppercase;font-size:13px;border-radius:2px">
    Open event →
  </a>
</div>
"""
    return _wrap(body, "Event Update")


def gift_ticket_html(recipient_name: str, gifter_name: str, event_title: str, event_when: str, event_where: str,
                     message: Optional[str], ticket_url: str, qr_url: str) -> str:
    note = f'<div style="margin:16px 0;padding:14px;border-left:3px solid #CCFF00;color:#e5e7eb;font-size:14px;font-style:italic">“{message}”<div style="font-size:11px;color:#71717a;margin-top:6px">— {gifter_name}</div></div>' if message else ""
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  You've got a ticket
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:20px">
  Hey {recipient_name}, <strong style="color:#fff">{gifter_name}</strong> bought you a ticket to <strong style="color:#fff">{event_title}</strong>.
</div>
{note}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="background:rgba(204,255,0,0.06);border:1px solid rgba(204,255,0,0.3);border-radius:4px;margin-bottom:24px">
  <tr><td style="padding:20px">
    <div style="font-size:11px;color:#CCFF00;letter-spacing:2px;text-transform:uppercase">Gift Ticket</div>
    <div style="font-family:Impact,Arial Black,sans-serif;font-size:24px;color:#fff;margin-top:6px">{event_title}</div>
    <div style="font-size:12px;color:#a1a1aa;margin-top:10px">📅 {event_when}</div>
    <div style="font-size:12px;color:#a1a1aa">📍 {event_where}</div>
  </td></tr>
  <tr><td align="center" style="padding:0 20px 20px">
    <img src="{qr_url}" width="180" height="180" alt="Your ticket QR" style="display:block;background:#fff;padding:8px;border-radius:4px" />
    <div style="font-size:11px;color:#71717a;margin-top:8px">Show this QR at the door</div>
  </td></tr>
</table>
<div style="margin-top:8px">
  <a href="{ticket_url}" style="display:inline-block;background:#CCFF00;color:#000;
     padding:12px 22px;text-decoration:none;font-family:Impact,Arial Black,sans-serif;
     letter-spacing:1px;text-transform:uppercase;font-size:13px;border-radius:2px">
    Open your ticket →
  </a>
</div>
<div style="font-size:11px;color:#71717a;margin-top:20px">
  No account needed. If you sign up to Art Core with this email, the ticket appears in your Tickets page automatically.
</div>
"""
    return _wrap(body, "You've got a ticket")


def gift_sent_html(gifter_name: str, recipient_email: str, event_title: str, amount: float, event_when: str) -> str:
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  Gift sent
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:24px">
  Hey {gifter_name}, we've emailed a ticket for <strong style="color:#fff">{event_title}</strong> ({event_when}) to <strong style="color:#fff">{recipient_email}</strong>.
</div>
<div style="font-size:12px;color:#CCFF00">Paid: ${amount:,.2f}</div>
<div style="font-size:11px;color:#71717a;margin-top:20px">Their QR ticket is attached to that email and also available from their Tickets page if they join Art Core.</div>
"""
    return _wrap(body, "Gift sent")


def gift_reminder_html(recipient_name: str, event_title: str, event_when: str, event_where: str, ticket_url: str, qr_url: str) -> str:
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  See you tomorrow
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:20px">
  Hey {recipient_name}, quick reminder — <strong style="color:#fff">{event_title}</strong> is tomorrow. Here's your ticket so you're not hunting for it at the door.
</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="background:rgba(204,255,0,0.06);border:1px solid rgba(204,255,0,0.3);border-radius:4px;margin-bottom:24px">
  <tr><td style="padding:20px">
    <div style="font-size:11px;color:#CCFF00;letter-spacing:2px;text-transform:uppercase">Your ticket</div>
    <div style="font-family:Impact,Arial Black,sans-serif;font-size:24px;color:#fff;margin-top:6px">{event_title}</div>
    <div style="font-size:12px;color:#a1a1aa;margin-top:10px">📅 {event_when}</div>
    <div style="font-size:12px;color:#a1a1aa">📍 {event_where}</div>
  </td></tr>
  <tr><td align="center" style="padding:0 20px 20px">
    <img src="{qr_url}" width="180" height="180" alt="Your ticket QR" style="display:block;background:#fff;padding:8px;border-radius:4px" />
    <div style="font-size:11px;color:#71717a;margin-top:8px">Show this QR at the door</div>
  </td></tr>
</table>
<div>
  <a href="{ticket_url}" style="display:inline-block;background:#CCFF00;color:#000;
     padding:12px 22px;text-decoration:none;font-family:Impact,Arial Black,sans-serif;
     letter-spacing:1px;text-transform:uppercase;font-size:13px;border-radius:2px">
    Open your ticket →
  </a>
</div>
"""
    return _wrap(body, "See you tomorrow")


def delivery_confirm_html(user_name: str, order_id: str, carrier: str, tracking: str, order_url: str, window_days: int) -> str:
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  Did your order arrive?
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:20px">Hey {user_name}, tracking shows your order <strong style="color:#fff">#{order_id[:8]}</strong> was delivered.</div>
<div style="font-family:Courier New,monospace;font-size:13px;color:#CCFF00;background:rgba(204,255,0,0.06);border:1px solid rgba(204,255,0,0.3);border-radius:4px;padding:14px;margin-bottom:20px">{carrier or '—'} · {tracking or '—'}</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:24px">Please open Art Core and tell us whether you <strong style="color:#fff">received it</strong> or <strong style="color:#FF4D4D">did not receive it</strong>. This protects you and the artist. If we don't hear from you within {window_days} days, the order is confirmed automatically.</div>
<a href="{order_url}" style="display:inline-block;background:#CCFF00;color:#000;padding:12px 22px;text-decoration:none;font-family:Impact,Arial Black,sans-serif;letter-spacing:1px;text-transform:uppercase;font-size:13px;border-radius:2px">Confirm delivery →</a>
"""
    return _wrap(body, "Did your order arrive?")


def otp_email_html(user_name: str, code: str, minutes: int) -> str:
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  Your sign-in code
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:24px">Hey {user_name}, use this code to finish signing in. It expires in {minutes} minutes.</div>
<div style="font-family:Courier New,monospace;font-size:40px;letter-spacing:10px;color:#CCFF00;background:rgba(204,255,0,0.06);border:1px solid rgba(204,255,0,0.3);border-radius:4px;padding:20px;text-align:center">{code}</div>
<div style="font-size:11px;color:#71717a;margin-top:20px">If you didn't try to sign in, change your password now — someone has it.</div>
"""
    return _wrap(body, "Your sign-in code")


def waiver_ending_html(user_name: str, tail: str, commission_percent: float) -> str:
    body = f"""
<div style="font-family:Impact,Arial Black,sans-serif;font-size:36px;color:#fff;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">
  Your 0% window {tail}
</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:24px">Hey {user_name}, heads up — your founding-artist window with <strong style="color:#fff">0% Art Core fees</strong> {tail}. After that the standard {commission_percent:g}% platform fee applies (card processing is unchanged).</div>
<div style="color:#a1a1aa;font-size:13px;margin-bottom:24px">Anything you sell before then is fee-free — a good moment to list the pieces you've been sitting on.</div>
<a href="https://artcorestudio.net/studio" style="display:inline-block;background:#CCFF00;color:#000;padding:12px 22px;text-decoration:none;font-family:Impact,Arial Black,sans-serif;letter-spacing:1px;text-transform:uppercase;font-size:13px;border-radius:2px">Open your studio →</a>
"""
    return _wrap(body, "Your 0% window is ending")
