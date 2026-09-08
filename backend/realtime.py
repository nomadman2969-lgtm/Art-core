"""In-process WebSocket hub — rooms `user:{id}` and `auction:{id}`. Falls back gracefully (clients keep slow polling)."""
import asyncio
import json
import logging
from typing import Dict, Set

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from auth import JWT_SECRET, JWT_ALG
from db import db, now_iso

router = APIRouter()
log = logging.getLogger(__name__)
_rooms: Dict[str, Set[WebSocket]] = {}


def _join(ws: WebSocket, room: str):
    _rooms.setdefault(room, set()).add(ws)


def _leave_all(ws: WebSocket):
    for room in list(_rooms):
        _rooms[room].discard(ws)
        if not _rooms[room]:
            _rooms.pop(room, None)


async def publish(room: str, payload: dict):
    """Fan out a JSON event to every socket in `room`. Never raises."""
    conns = list(_rooms.get(room, ()))
    if not conns:
        return
    data = json.dumps({**payload, "room": room, "at": now_iso()})
    for ws in conns:
        try:
            await ws.send_text(data)
        except Exception:
            _rooms.get(room, set()).discard(ws)


def publish_soon(room: str, payload: dict):
    try:
        asyncio.get_running_loop().create_task(publish(room, payload))
    except RuntimeError:
        pass


@router.websocket("/api/ws")
async def ws_endpoint(ws: WebSocket, token: str = Query(default=""), rooms: str = Query(default="")):
    user_id = None
    if token:
        try:
            user_id = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])["sub"]
        except jwt.PyJWTError:
            user_id = None
    await ws.accept()
    if user_id:
        _join(ws, f"user:{user_id}")
    for r in filter(None, rooms.split(",")):
        if r.startswith("auction:"):
            _join(ws, r)
    await ws.send_text(json.dumps({"type": "hello", "user_id": user_id}))
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("type") == "join" and str(msg.get("room", "")).startswith("auction:"):
                _join(ws, msg["room"])
            elif msg.get("type") == "ping":
                await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa
        log.debug("ws closed: %s", e)
    finally:
        _leave_all(ws)
