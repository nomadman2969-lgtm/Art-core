"""Claude Listing Assistant — photo (+ hints) → draft title, description, medium, tags, price range."""
import base64
import json
import os
import re
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from db import db, new_id, now_iso
from auth import get_current_user

router = APIRouter(prefix="/api/studio", tags=["listing-assist"])
MEDIUMS = ["Oil", "Acrylic", "Watercolor", "Mixed Media", "Digital", "Photography", "Sculpture", "Print"]
FURNITURE = ["chair", "table", "dresser", "cabinet", "lamp", "mirror", "shelf", "bench", "other"]


class AssistReq(BaseModel):
    image_path: str = Field(min_length=3)
    section: str = Field(default="art", pattern="^(art|upcycle)$")
    hints: Optional[str] = Field(default=None, max_length=600)
    width_in: Optional[float] = None
    height_in: Optional[float] = None
    kind: Optional[str] = None


SYSTEM = """You are the Art Core Listing Assistant: a gallery copywriter and pricing analyst for independent artists selling originals online.
Look at the artwork photo and the artist's hints. Return ONLY a JSON object, no prose, with keys:
title (string, 2-6 words, evocative, no quotes), description (string, 60-120 words, second person to the collector, concrete about colour/texture/subject/mood, no hype words like 'stunning'),
medium (one of: %s), style (short, e.g. 'abstract expressionism'), color (dominant palette in 2-4 words), tags (array of 5-8 lowercase single or hyphenated words),
price_low (number USD), price_high (number USD), price_note (one sentence explaining the range for an emerging independent artist selling direct, considering size, medium and detail),
furniture_type (only for upcycle; one of: %s), materials (only for upcycle; short comma list).
Price guidance: emerging artists direct-to-collector. Small works on paper $60-250, small canvases $150-600, medium canvases $400-1500, large statement pieces $1200-4000, upcycled furniture $150-900. Adjust for detail and medium. Never exceed $6000.""" % (", ".join(MEDIUMS), ", ".join(FURNITURE))


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no json")
    return json.loads(m.group(0))


@router.post("/listing-assist")
async def listing_assist(req: AssistReq, user: dict = Depends(get_current_user)):
    if user["role"] not in ("artist", "admin"):
        raise HTTPException(403, "Artists only")
    clean = req.image_path.replace("/api/files/", "").lstrip("/")
    rec = await db.files.find_one({"storage_path": clean, "is_deleted": False})
    if not rec or (rec.get("user_id") != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "Upload the image first")
    from storage import get_object
    from PIL import Image
    import io
    try:
        raw, ctype = get_object(clean)[:2]
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.thumbnail((1024, 1024))
        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        raise HTTPException(400, "Could not read that image")

    hints = []
    if req.hints: hints.append(f"Artist notes: {req.hints.strip()}")
    if req.width_in and req.height_in: hints.append(f"Size: {req.width_in:g} x {req.height_in:g} inches")
    if req.kind: hints.append(f"Type: {req.kind}")
    hints.append("Section: upcycled furniture piece" if req.section == "upcycle" else "Section: fine art")
    prompt = "Draft the listing for this piece.\n" + "\n".join(hints)

    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"listing-{user['id']}-{new_id()[:8]}", system_message=SYSTEM).with_model("anthropic", "claude-sonnet-4-6")
    try:
        text = await chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(image_base64=b64)]))
        data = _extract_json(str(text))
    except Exception as e:
        raise HTTPException(502, f"Assistant unavailable: {str(e)[:120]}")

    out = {
        "title": str(data.get("title") or "")[:80].strip(),
        "description": str(data.get("description") or "")[:1200].strip(),
        "medium": data.get("medium") if data.get("medium") in MEDIUMS else ("Mixed Media" if req.section == "upcycle" else "Acrylic"),
        "style": str(data.get("style") or "")[:60],
        "color": str(data.get("color") or "")[:60],
        "tags": [str(t).lower().strip()[:24] for t in (data.get("tags") or []) if str(t).strip()][:8],
        "price_low": max(10, int(float(data.get("price_low") or 0))),
        "price_high": max(10, int(float(data.get("price_high") or 0))),
        "price_note": str(data.get("price_note") or "")[:300],
        "furniture_type": data.get("furniture_type") if data.get("furniture_type") in FURNITURE else None,
        "materials": str(data.get("materials") or "")[:120] or None,
    }
    if out["price_high"] < out["price_low"]:
        out["price_low"], out["price_high"] = out["price_high"], out["price_low"]
    out["price_suggested"] = int(round((out["price_low"] + out["price_high"]) / 2 / 5) * 5)
    await db.listing_assists.insert_one({"id": new_id(), "user_id": user["id"], "image_path": clean, "section": req.section, "result": out, "created_at": now_iso()})
    return out
