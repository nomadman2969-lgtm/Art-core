"""Wallet-style ticket pass renderer: a phone-sized PNG (QR + event details) users save to their lock screen / Photos.
Native Apple Wallet (.pkpass) and Google Wallet require developer signing credentials — this is the credential-free fallback."""
import io
from datetime import datetime
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
LIME = (204, 255, 0)
BG = (10, 10, 12)
CARD = (18, 18, 20)
ZINC = (161, 161, 170)
DIM = (113, 113, 122)
FONT_DIR = "/usr/share/fonts/truetype"


def _font(size: int, bold: bool = False, cjk: bool = False):
    candidates = (["noto/NotoSansCJK-Bold.ttc", "noto/NotoSansCJK-Regular.ttc", "wqy/wqy-microhei.ttc"] if cjk else []) + [
        "liberation/LiberationSans-Bold.ttf" if bold else "liberation/LiberationSans-Regular.ttf",
        "dejavu/DejaVuSans-Bold.ttf" if bold else "dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(f"{FONT_DIR}/{c}", size)
        except Exception:
            continue
    return ImageFont.load_default()


def _needs_cjk(s: str) -> bool:
    return any(ord(ch) > 0x2E80 for ch in s or "")


def _wrap(draw, text, font, max_w):
    words, lines, cur = (text or "").split(" "), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def _fmt_when(iso: str) -> str:
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00")).strftime("%a, %b %d · %-I:%M %p")
    except Exception:
        return iso or "TBA"


def render_pass(event_title: str, start_at: str, where: str, holder: str, qr_png: Optional[bytes], rsvp_id: str, subtitle: str = "Ticket") -> bytes:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    cjk = _needs_cjk(event_title) or _needs_cjk(holder)
    # card
    d.rounded_rectangle((60, 220, W - 60, H - 120), radius=48, fill=CARD, outline=(40, 40, 44), width=3)
    d.rectangle((60, 220, W - 60, 236), fill=LIME)
    # brand
    d.text((110, 300), "ART", font=_font(72, bold=True), fill=(255, 255, 255))
    d.text((110 + d.textlength("ART ", font=_font(72, bold=True)), 300), "CORE", font=_font(72, bold=True), fill=LIME)
    d.text((110, 400), subtitle.upper(), font=_font(30, bold=True), fill=LIME)
    # title
    y = 460
    for line in _wrap(d, event_title, _font(78, bold=True, cjk=cjk), W - 220):
        d.text((110, y), line, font=_font(78, bold=True, cjk=cjk), fill=(255, 255, 255))
        y += 92
    y += 30
    d.text((110, y), _fmt_when(start_at), font=_font(40), fill=ZINC); y += 60
    for line in _wrap(d, where, _font(40, cjk=_needs_cjk(where)), W - 220)[:2]:
        d.text((110, y), line, font=_font(40, cjk=_needs_cjk(where)), fill=ZINC); y += 56
    # perforation
    py = max(y + 60, 900)
    for x in range(110, W - 110, 36):
        d.line((x, py, x + 18, py), fill=(60, 60, 66), width=4)
    # QR
    qr_size = 620
    qx, qy = (W - qr_size) // 2, py + 70
    d.rounded_rectangle((qx - 30, qy - 30, qx + qr_size + 30, qy + qr_size + 30), radius=32, fill=(255, 255, 255))
    if qr_png:
        try:
            q = Image.open(io.BytesIO(qr_png)).convert("RGB").resize((qr_size, qr_size), Image.NEAREST)
            img.paste(q, (qx, qy))
        except Exception:
            pass
    ty = qy + qr_size + 80
    d.text((W // 2, ty), "SHOW AT THE DOOR", font=_font(30, bold=True), fill=LIME, anchor="mm")
    d.text((W // 2, ty + 60), holder, font=_font(40, cjk=cjk), fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, ty + 120), f"ID {rsvp_id[:8].upper()}", font=_font(28), fill=DIM, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
