"""Certificate of Authenticity — PDF per purchased artwork with QR back to the artwork page."""
import io
import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from db import db
from auth import get_current_user

router = APIRouter(prefix="/api", tags=["certificates"])
BG, INK, LIME, MUTED = "#0A0A0C", "#F4F4F5", "#CCFF00", "#71717A"


def _cert_id(order_id: str, artwork_id: str) -> str:
    return f"AC-{order_id.replace('order_', '')[:8].upper()}-{artwork_id[:6].upper()}"


def _build_pdf(order: dict, art: dict, artist: dict, buyer: dict, image_bytes: bytes | None, url: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    import qrcode

    buf = io.BytesIO()
    W, H = letter
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFillColor(HexColor(BG)); c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setStrokeColor(HexColor(LIME)); c.setLineWidth(3); c.rect(0.4 * inch, 0.4 * inch, W - 0.8 * inch, H - 0.8 * inch, stroke=1, fill=0)

    c.setFillColor(HexColor(INK)); c.setFont("Helvetica-Bold", 30); c.drawString(0.9 * inch, H - 1.25 * inch, "ART")
    c.setFillColor(HexColor(LIME)); c.drawString(0.9 * inch + 68, H - 1.25 * inch, "CORE")
    c.setFillColor(HexColor(MUTED)); c.setFont("Helvetica", 9)
    c.drawString(0.9 * inch, H - 1.5 * inch, "C E R T I F I C A T E   O F   A U T H E N T I C I T Y")

    cert_id = _cert_id(order["id"], art["id"])
    c.setFont("Helvetica", 8); c.drawRightString(W - 0.9 * inch, H - 1.25 * inch, f"No. {cert_id}")

    img_top = H - 1.9 * inch
    img_h = 3.6 * inch
    if image_bytes:
        try:
            img = ImageReader(io.BytesIO(image_bytes))
            iw, ih = img.getSize()
            scale = min((W - 1.8 * inch) / iw, img_h / ih)
            dw, dh = iw * scale, ih * scale
            c.drawImage(img, (W - dw) / 2, img_top - dh, dw, dh, mask="auto")
        except Exception:
            pass
    y = img_top - img_h - 0.45 * inch

    c.setFillColor(HexColor(INK)); c.setFont("Helvetica-Bold", 22)
    c.drawString(0.9 * inch, y, (art.get("title") or "Untitled")[:60]); y -= 0.3 * inch
    c.setFillColor(HexColor(LIME)); c.setFont("Helvetica", 12)
    c.drawString(0.9 * inch, y, f"by {artist.get('name', 'Unknown artist')}"); y -= 0.45 * inch

    kind = (art.get("kind") or "original").capitalize()
    edition = f"{kind}" if kind != "Print" else f"Limited edition print · edition of {art.get('quantity') or 1}"
    rows = [
        ("Medium", art.get("medium") or "—"),
        ("Dimensions", f"{art.get('width_in')} × {art.get('height_in')} in"),
        ("Year", str(art.get("year") or "—")),
        ("Edition", edition),
        ("Acquired by", buyer.get("name") or "—"),
        ("Sale date", (order.get("created_at") or "")[:10]),
        ("Order", order["id"]),
    ]
    c.setFont("Helvetica", 10)
    for label, val in rows:
        c.setFillColor(HexColor(MUTED)); c.drawString(0.9 * inch, y, label.upper())
        c.setFillColor(HexColor(INK)); c.drawString(2.4 * inch, y, str(val)[:70]); y -= 0.26 * inch

    qr = qrcode.make(url, box_size=6, border=1)
    qb = io.BytesIO(); qr.save(qb, format="PNG")
    c.drawImage(ImageReader(io.BytesIO(qb.getvalue())), W - 2.4 * inch, 1.1 * inch, 1.4 * inch, 1.4 * inch)
    c.setFillColor(HexColor(MUTED)); c.setFont("Helvetica", 7)
    c.drawString(W - 2.4 * inch, 0.95 * inch, "Scan to verify provenance")

    c.setStrokeColor(HexColor(INK)); c.setLineWidth(0.6); c.line(0.9 * inch, 1.55 * inch, 3.9 * inch, 1.55 * inch)
    c.setFont("Helvetica-Oblique", 14); c.setFillColor(HexColor(INK)); c.drawString(0.95 * inch, 1.62 * inch, artist.get("name", ""))
    c.setFont("Helvetica", 8); c.setFillColor(HexColor(MUTED)); c.drawString(0.9 * inch, 1.38 * inch, "ARTIST SIGNATURE")
    c.drawString(0.9 * inch, 0.62 * inch, "This certifies the work above is an authentic piece sold through Art Core. Issued digitally · artcorestudio.net")
    c.showPage(); c.save()
    return buf.getvalue()


@router.get("/orders/{oid}/certificate/{artwork_id}")
async def certificate(oid: str, artwork_id: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"id": oid})
    if not o:
        raise HTTPException(404, "Order not found")
    is_buyer = o.get("buyer_id") == user["id"]
    is_seller = any(p["artist_id"] == user["id"] for p in o.get("artist_payouts", []))
    if not (is_buyer or is_seller or user.get("role") == "admin"):
        raise HTTPException(403, "Not your order")
    if o.get("refunded"):
        raise HTTPException(400, "Order was refunded — certificate void")
    item = next((it for it in o.get("items", []) if it["artwork_id"] == artwork_id), None)
    if not item:
        raise HTTPException(404, "Artwork not in this order")
    art = await db.artworks.find_one({"id": artwork_id}) or {"id": artwork_id, "title": "Artwork"}
    artist = await db.users.find_one({"id": item["artist_id"]}) or {}
    buyer = await db.users.find_one({"id": o.get("buyer_id")}) or {}
    image_bytes = None
    if art.get("images"):
        try:
            from storage import get_object
            image_bytes, _ = get_object(art["images"][0])
        except Exception:
            image_bytes = None
    origin = os.environ.get("PUBLIC_APP_URL", "https://artcorestudio.net")
    pdf = _build_pdf(o, art, artist, buyer, image_bytes, f"{origin}/artwork/{artwork_id}?cert={_cert_id(o['id'], artwork_id)}")
    fname = f"ArtCore_COA_{_cert_id(o['id'], artwork_id)}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
