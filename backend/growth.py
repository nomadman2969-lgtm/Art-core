"""Growth features: achievement badges, OG share cards, onboarding flag."""
import html as _h
import io
import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response
from db import db, now_iso, strip_mongo
from auth import get_current_user

router = APIRouter(prefix="/api", tags=["growth"])
APP_URL = os.environ.get("PUBLIC_APP_URL", "https://artcorestudio.net")

BADGES = [
    ("first_sale", "First Sale", "Sold a first original", "#CCFF00"),
    ("ten_sales", "Ten Sales", "Ten works in private collections", "#CCFF00"),
    ("auction_closer", "Auction Closer", "Won a bidding war as the seller", "#7C3AED"),
    ("commissioned", "Commissioned", "Completed a paid commission", "#F5A623"),
    ("event_host", "Event Host", "Hosted an event on Art Core", "#00E5FF"),
    ("sold_out_show", "Sold-Out Show", "Filled every seat at an event", "#FF4D4D"),
    ("rising", "Rising", "10 followers", "#FF6EC7"),
    ("hundred_club", "100 Club", "100 followers", "#D4AF37"),
    ("five_star", "Five Star", "A 5-star collector review", "#CCFF00"),
]


@router.get("/users/{user_id}/badges")
async def badges(user_id: str):
    sold = await db.orders.count_documents({"artist_payouts.artist_id": user_id, "refunded": {"$ne": True}})
    followers = await db.follows.count_documents({"followed_id": user_id})
    auction_sold = await db.auctions.count_documents({"seller_id": user_id, "status": "ended", "winner_id": {"$ne": None}})
    commissions = await db.commissions.count_documents({"artist_id": user_id, "status": {"$in": ["approved", "paid"]}})
    hosted = await db.events.find({"host_id": user_id, "cancelled": {"$ne": True}}).to_list(200)
    sold_out = False
    for e in hosted:
        if e.get("max_capacity") and await db.event_rsvps.count_documents({"event_id": e["id"]}) >= e["max_capacity"]:
            sold_out = True
            break
    five_star = await db.reviews.count_documents({"artist_id": user_id, "rating": 5})
    earned = {
        "first_sale": sold >= 1, "ten_sales": sold >= 10, "auction_closer": auction_sold >= 1,
        "commissioned": commissions >= 1, "event_host": len(hosted) >= 1, "sold_out_show": sold_out,
        "rising": followers >= 10, "hundred_club": followers >= 100, "five_star": five_star >= 1,
    }
    return [{"id": i, "label": l, "desc": d, "color": c, "earned": earned[i]} for i, l, d, c in BADGES]


@router.post("/onboarding/complete")
async def onboarding_complete(user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"onboarded": True, "onboarded_at": now_iso()}})
    return {"ok": True}


# ---------- Share cards (server-rendered OG tags for crawlers, JS redirect for humans) ----------
def _share_html(title: str, desc: str, image: str, target: str) -> str:
    t, d, image, target = _h.escape(title), _h.escape(desc[:200]), _h.escape(image), _h.escape(target)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{t} · Art Core</title>
<meta property="og:type" content="website"><meta property="og:site_name" content="Art Core">
<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">
<meta property="og:image" content="{image}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:url" content="{target}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{t}"><meta name="twitter:description" content="{d}"><meta name="twitter:image" content="{image}">
<meta http-equiv="refresh" content="0;url={target}"><script>location.replace({target!r})</script>
<style>body{{background:#0A0A0C;color:#e5e7eb;font-family:Helvetica,Arial;padding:40px}}a{{color:#CCFF00}}</style></head>
<body><p>Opening <a href="{target}">{t}</a> on Art Core…</p></body></html>"""


def _og_png(image_bytes: bytes | None, title: str, subtitle: str, accent: str = "#CCFF00") -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    card = Image.new("RGB", (W, H), "#0A0A0C")
    if image_bytes:
        try:
            art = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            box = (560, 530)
            art.thumbnail(box)
            card.paste(art, (W - art.width - 60, (H - art.height) // 2))
        except Exception:
            pass
    d = ImageDraw.Draw(card)
    def font(size, bold=True):
        for path in ("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default(size=size)
    f_brand, f_title, f_sub = font(34), font(52), font(26, bold=False)
    d.text((60, 56), "ART", fill="#FFFFFF", font=f_brand)
    d.text((60 + d.textlength("ART ", font=f_brand), 56), "CORE", fill=accent, font=f_brand)
    d.rectangle((60, 112, 120, 116), fill=accent)
    words, lines, cur = title.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if d.textlength(test, font=f_title) > 500 and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    lines.append(cur)
    y = 200
    for line in lines[:4]:
        d.text((60, y), line, fill="#FFFFFF", font=f_title); y += 62
    d.text((60, y + 14), subtitle[:60], fill=accent, font=f_sub)
    d.text((60, H - 80), "artcorestudio.net", fill="#71717A", font=f_sub)
    out = io.BytesIO(); card.save(out, format="PNG", optimize=True)
    return out.getvalue()


async def _first_image(path: str | None) -> bytes | None:
    if not path:
        return None
    try:
        from storage import get_object
        return get_object(path)[0]
    except Exception:
        return None


@router.get("/share/artwork/{aid}", response_class=HTMLResponse)
async def share_artwork(aid: str):
    a = await db.artworks.find_one({"id": aid})
    if not a:
        raise HTTPException(404, "Not found")
    artist = await db.users.find_one({"id": a["artist_id"]}) or {}
    desc = f"{a.get('medium', '')} · {a.get('width_in')}×{a.get('height_in')} in · ${float(a.get('price') or 0):,.0f} — by {artist.get('name', 'an Art Core artist')}"
    return _share_html(a["title"], desc, f"{APP_URL}/api/share/og/artwork/{aid}.png", f"{APP_URL}/artwork/{aid}")


@router.get("/share/studio/{uid}", response_class=HTMLResponse)
async def share_studio(uid: str):
    u = await db.users.find_one({"id": uid})
    if not u:
        raise HTTPException(404, "Not found")
    return _share_html(f"{u['name']} · Studio", u.get("bio") or "Explore this artist's studio on Art Core.",
                       f"{APP_URL}/api/share/og/studio/{uid}.png", f"{APP_URL}/artist/{uid}")


@router.get("/share/event/{eid}", response_class=HTMLResponse)
async def share_event(eid: str):
    e = await db.events.find_one({"id": eid})
    if not e:
        raise HTTPException(404, "Not found")
    loc = e.get("location") or {}
    when = (e.get("start_at") or "")[:16].replace("T", " ")
    price = "Free" if e.get("is_free") else f"${e.get('ticket_price')}"
    where = e.get("venue") or loc.get("address") or ""
    desc = f"{when} · {where} {loc.get('city') or ''} · {price} — hosted by {e.get('host_name', '')}"
    return _share_html(e["title"], desc, f"{APP_URL}/api/share/og/event/{eid}.png", f"{APP_URL}/events/{eid}")


@router.get("/share/og/event/{eid}.png")
async def og_event(eid: str):
    e = await db.events.find_one({"id": eid})
    if not e:
        raise HTTPException(404, "Not found")
    loc = e.get("location") or {}
    when = (e.get("start_at") or "")[:10]
    png = _og_png(await _first_image(e.get("cover_image")), e["title"], f"{when} · {loc.get('city') or e.get('venue') or ''}", accent="#FF4D4D")
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/share/og/artwork/{aid}.png")
async def og_artwork(aid: str):
    a = await db.artworks.find_one({"id": aid})
    if not a:
        raise HTTPException(404, "Not found")
    artist = await db.users.find_one({"id": a["artist_id"]}) or {}
    img = await _first_image((a.get("images") or [None])[0])
    png = _og_png(img, a["title"], f"by {artist.get('name', '')} · ${float(a.get('price') or 0):,.0f}")
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/share/og/studio/{uid}.png")
async def og_studio(uid: str):
    u = await db.users.find_one({"id": uid})
    if not u:
        raise HTTPException(404, "Not found")
    cover = u.get("cover_image") or u.get("avatar")
    if not cover:
        first = await db.artworks.find_one({"artist_id": uid, "images.0": {"$exists": True}})
        cover = (first or {}).get("images", [None])[0]
    cfg = await db.studio_configs.find_one({"artist_id": uid}) or {}
    style = (cfg.get("artist_story") or {}).get("style") or "Artist Studio"
    png = _og_png(await _first_image(cover), u["name"], style)
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
