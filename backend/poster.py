"""Printable flyer poster (PNG, 1080×1620 — 2:3) for an event, with a QR code to its launch page."""
import io
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from db import db

router = APIRouter(prefix="/api", tags=["poster"])
APP_URL = os.environ.get("PUBLIC_APP_URL", "https://artcorestudio.net")
W, H = 1080, 1620
BG, LIME, CARD = (10, 10, 12), (204, 255, 0), (17, 17, 19)


def _cover(path):
    if not path:
        return None
    try:
        from storage import get_object
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(get_object(path)[0])).convert("RGB")
        return ImageOps.fit(img, (W, 720), centering=(0.5, 0.4))
    except Exception:
        return None


def render_poster(e: dict, url: str) -> bytes:
    from PIL import Image, ImageDraw
    import qrcode
    from wallet_pass import _font, _wrap, _needs_cjk
    from emails import _fmt_when
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    cover = _cover(e.get("cover_image"))
    if cover:
        img.paste(cover, (0, 0))
        fade = Image.new("L", (W, 720), 0)
        fd = ImageDraw.Draw(fade)
        for y in range(720):
            fd.line((0, y, W, y), fill=int(255 * max(0, (y - 360) / 360)))
        img.paste(Image.new("RGB", (W, 720), BG), (0, 0), fade)
    d.rectangle((0, 0, W, 14), fill=LIME)
    d.text((70, 60), "ART", font=_font(54, bold=True), fill=(255, 255, 255))
    d.text((70 + d.textlength("ART ", font=_font(54, bold=True)), 60), "CORE", font=_font(54, bold=True), fill=LIME)
    d.text((70, 130), ((e.get("category") or "event").replace("_", " ") + "  ·  " + ("FREE" if e.get("is_free", True) else f"${float(e.get('ticket_price') or 0):,.0f}")).upper(),
           font=_font(26, bold=True), fill=LIME)
    cjk = _needs_cjk(e.get("title", ""))
    y = 700 if cover else 260
    title_font = _font(92, bold=True, cjk=cjk)
    for line in _wrap(d, e.get("title", "Art Core Event"), title_font, W - 140)[:3]:
        d.text((70, y), line, font=title_font, fill=(255, 255, 255)); y += 104
    y += 20
    loc = e.get("location") or {}
    where = ", ".join(x for x in [e.get("venue"), loc.get("address"), loc.get("city")] if x) or "Location on the event page"
    d.text((70, y), _fmt_when(e.get("start_at")), font=_font(40, bold=True), fill=LIME); y += 60
    for line in _wrap(d, where, _font(32), W - 140)[:2]:
        d.text((70, y), line, font=_font(32), fill=(190, 190, 200)); y += 44
    host = e.get("organizer") or e.get("host_name")
    if host:
        d.text((70, y + 6), f"Hosted by {host}", font=_font(28), fill=(140, 140, 150)); y += 50
    # QR block
    qy = H - 520
    d.rounded_rectangle((70, qy, W - 70, H - 70), radius=32, fill=CARD, outline=(40, 40, 44), width=3)
    qr = qrcode.QRCode(border=1, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url); qr.make(fit=True)
    qimg = qr.make_image(fill_color="black", back_color="white").convert("RGB").resize((360, 360))
    img.paste(qimg, (110, qy + 45))
    tx = 520
    d.text((tx, qy + 70), "SCAN FOR YOUR", font=_font(34, bold=True), fill=(255, 255, 255))
    d.text((tx, qy + 115), "FREE TICKET" if e.get("is_free", True) else "TICKET", font=_font(52, bold=True), fill=LIME)
    for i, line in enumerate(_wrap(d, "Meet the artists. Buy originals. Join the Art Core community.", _font(26), W - tx - 110)[:3]):
        d.text((tx, qy + 200 + i * 36), line, font=_font(26), fill=(170, 170, 180))
    d.text((tx, qy + 340), url.replace("https://", ""), font=_font(24), fill=(113, 113, 122))
    out = io.BytesIO(); img.save(out, format="PNG", optimize=True)
    return out.getvalue()


@router.get("/events/{eid}/poster.png")
async def event_poster(eid: str):
    e = await db.events.find_one({"id": eid})
    if not e or e.get("cancelled"):
        raise HTTPException(404, "Not found")
    host = await db.users.find_one({"id": e.get("host_id")}) if e.get("host_id") else None
    if host and not e.get("organizer"):
        e["host_name"] = host.get("name")
    png = render_poster(e, f"{APP_URL}/launch/{eid}")
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=600",
                                                          "Content-Disposition": f'inline; filename="artcore-flyer-{eid[:8]}.png"'})
