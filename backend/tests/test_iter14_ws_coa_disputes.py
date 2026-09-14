"""Iter 14 backend tests — WebSocket realtime (bids + DM/typing), Certificate of Authenticity PDF, Order Disputes."""
import asyncio
import json
import os
import pytest
import requests

try:
    import websockets
except ImportError:
    websockets = None


def _read_frontend_backend_url():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE = os.environ.get("REACT_APP_BACKEND_URL", _read_frontend_backend_url()).rstrip("/")
API = f"{BASE}/api"
WS_HOST = BASE.replace("https://", "").replace("http://", "")
WS_SCHEME = "wss" if BASE.startswith("https") else "ws"

DEMO_ARTIST = ("demo.artist@artcorestudio.net", "DemoArtist2026!")
DEMO_COLLECTOR = ("demo.collector@artcorestudio.net", "DemoCollector2026!")
ADMIN = ("monster@houseofmonster.com", os.environ["ADMIN_PASSWORD"])

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20, headers=UA)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    j = r.json()
    return j["token"], j["user"]


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json", **UA}


@pytest.fixture(scope="module")
def collector_ctx():
    return login(*DEMO_COLLECTOR)


@pytest.fixture(scope="module")
def artist_ctx():
    return login(*DEMO_ARTIST)


@pytest.fixture(scope="module")
def admin_ctx():
    return login(*ADMIN)


# ---------- WEBSOCKET ----------
class TestWebSocket:
    def test_ws_hello_and_ping(self, collector_ctx):
        assert websockets, "websockets library required"
        tok, u = collector_ctx

        async def run():
            url = f"{WS_SCHEME}://{WS_HOST}/api/ws?token={tok}"
            async with websockets.connect(url) as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                assert hello["type"] == "hello"
                assert hello["user_id"] == u["id"]
                await ws.send(json.dumps({"type": "ping"}))
                pong = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert pong["type"] == "pong"

        asyncio.run(run())

    def test_ws_invalid_token_hello_null(self):
        assert websockets

        async def run():
            url = f"{WS_SCHEME}://{WS_HOST}/api/ws?token=bogus"
            async with websockets.connect(url) as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                assert hello["type"] == "hello"
                assert hello["user_id"] is None

        asyncio.run(run())

    def test_ws_auction_bid_broadcast(self, collector_ctx):
        assert websockets
        tok, u = collector_ctx
        r = requests.get(f"{API}/auctions?status=live", headers=UA, timeout=15)
        assert r.status_code == 200
        auctions = r.json()
        calor = next((a for a in auctions if "Calor" in ((a.get("artwork") or {}).get("title") or a.get("title") or "")), None)
        if not calor:
            pytest.skip("Calor auction not live currently")
        aid = calor["id"]
        current = float(calor.get("current_bid") or calor.get("starting_bid") or 0)
        bid_amount = current + 25
        # Ensure bid stays safely below reserve 2000
        assert bid_amount < 2000, f"bid {bid_amount} would exceed reserve"

        async def run():
            url = f"{WS_SCHEME}://{WS_HOST}/api/ws?token={tok}&rooms=auction:{aid}"
            async with websockets.connect(url) as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                assert hello["type"] == "hello"
                # Place the bid via HTTP
                rb = requests.post(f"{API}/auctions/{aid}/bid",
                                   headers=H(tok), json={"amount": bid_amount}, timeout=15)
                assert rb.status_code in (200, 201), f"bid: {rb.status_code} {rb.text}"
                # Wait for bid event
                for _ in range(10):
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                    if msg.get("type") == "bid":
                        assert float(msg.get("amount")) == pytest.approx(bid_amount)
                        return
                pytest.fail("Never received bid event over WS")

        asyncio.run(run())

    def test_ws_dm_and_typing(self, collector_ctx, artist_ctx):
        assert websockets
        c_tok, c_user = collector_ctx
        a_tok, a_user = artist_ctx

        async def run():
            url = f"{WS_SCHEME}://{WS_HOST}/api/ws?token={a_tok}"
            async with websockets.connect(url) as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                assert hello["user_id"] == a_user["id"]
                # Collector posts a DM to artist
                rm = requests.post(f"{API}/messages", headers=H(c_tok),
                                   json={"to_user_id": a_user["id"], "text": "ws check"}, timeout=15)
                assert rm.status_code in (200, 201), rm.text
                got_dm = False
                got_typing = False
                # Signal typing
                rt = requests.post(f"{API}/messages/thread/{a_user['id']}/typing",
                                   headers=H(c_tok), json={}, timeout=15)
                assert rt.status_code in (200, 204), rt.text
                for _ in range(15):
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=6))
                    except asyncio.TimeoutError:
                        break
                    if msg.get("type") == "dm" and msg.get("from_id") == c_user["id"]:
                        got_dm = True
                    if msg.get("type") == "typing" and msg.get("from_id") == c_user["id"]:
                        got_typing = True
                    if got_dm and got_typing:
                        break
                assert got_dm, "DM event not delivered over WS"
                assert got_typing, "typing event not delivered over WS"

        asyncio.run(run())


# ---------- CERTIFICATE OF AUTHENTICITY ----------
def _find_delivered_order(tok):
    r = requests.get(f"{API}/orders/mine", headers=H(tok), timeout=15)
    assert r.status_code == 200
    for o in r.json():
        f = o.get("fulfillment") or {}
        if f.get("status") == "delivered" and o.get("items"):
            return o
    return None


def _find_shipped_order(tok):
    r = requests.get(f"{API}/orders/mine", headers=H(tok), timeout=15)
    assert r.status_code == 200
    for o in r.json():
        f = o.get("fulfillment") or {}
        if f.get("status") == "shipped" and o.get("items"):
            return o
    return None


class TestCertificate:
    def test_coa_success(self, collector_ctx):
        tok, _ = collector_ctx
        o = _find_delivered_order(tok)
        assert o, "no delivered order for demo collector"
        aid = o["items"][0]["artwork_id"]
        r = requests.get(f"{API}/orders/{o['id']}/certificate/{aid}", headers=H(tok), timeout=30)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert "attachment" in r.headers.get("content-disposition", "").lower()

    def test_coa_unauthenticated(self, collector_ctx):
        tok, _ = collector_ctx
        o = _find_delivered_order(tok)
        assert o
        aid = o["items"][0]["artwork_id"]
        r = requests.get(f"{API}/orders/{o['id']}/certificate/{aid}", headers=UA, timeout=15)
        assert r.status_code == 401

    def test_coa_wrong_artwork(self, collector_ctx):
        tok, _ = collector_ctx
        o = _find_delivered_order(tok)
        assert o
        r = requests.get(f"{API}/orders/{o['id']}/certificate/does-not-exist",
                         headers=H(tok), timeout=15)
        assert r.status_code == 404

    def test_coa_non_party_forbidden(self, collector_ctx, artist_ctx):
        # Find an order whose seller is NOT demo artist and buyer is collector
        c_tok, _ = collector_ctx
        a_tok, a_user = artist_ctx
        r = requests.get(f"{API}/orders/mine", headers=H(c_tok), timeout=15)
        target = None
        for o in r.json():
            payouts = o.get("artist_payouts") or []
            if payouts and all(p.get("artist_id") != a_user["id"] for p in payouts) and o.get("items"):
                target = o
                break
        if not target:
            pytest.skip("No order where demo artist is not a seller")
        aid = target["items"][0]["artwork_id"]
        r2 = requests.get(f"{API}/orders/{target['id']}/certificate/{aid}",
                          headers=H(a_tok), timeout=15)
        assert r2.status_code == 403


# ---------- DISPUTES ----------
class TestDisputes:
    def _get_or_open_dispute(self, tok, order_id):
        """Ensure there's an OPEN dispute (creating if previous is resolved)."""
        r = requests.get(f"{API}/orders/{order_id}/dispute", headers=H(tok), timeout=15)
        assert r.status_code == 200
        existing = r.json()
        if existing and existing.get("status") in ("open", "under_review"):
            return existing
        # open a new one
        r2 = requests.post(f"{API}/orders/{order_id}/dispute", headers=H(tok),
                           json={"reason": "not_as_described",
                                 "description": "Iter14 auto-test: item does not match listing photos."},
                           timeout=15)
        assert r2.status_code in (200, 201), r2.text
        return r2.json()

    def test_dispute_full_flow(self, collector_ctx, artist_ctx, admin_ctx):
        c_tok, c_user = collector_ctx
        a_tok, a_user = artist_ctx
        adm_tok, _ = admin_ctx

        o = _find_shipped_order(c_tok)
        assert o, "no shipped order for demo collector"
        oid = o["id"]

        d = self._get_or_open_dispute(c_tok, oid)
        assert d["status"] in ("open", "under_review")
        assert d.get("buyer") and d.get("seller") is not None
        assert d.get("artwork") is not None
        did = d["id"]

        # Duplicate open → 400
        r_dup = requests.post(f"{API}/orders/{oid}/dispute", headers=H(c_tok),
                              json={"reason": "damaged", "description": "duplicate attempt"},
                              timeout=15)
        assert r_dup.status_code == 400

        # description < 10 → 422
        r_short = requests.post(f"{API}/orders/{oid}/dispute", headers=H(c_tok),
                                json={"reason": "damaged", "description": "short"},
                                timeout=15)
        assert r_short.status_code == 422

        # invalid reason → 422
        r_bad = requests.post(f"{API}/orders/{oid}/dispute", headers=H(c_tok),
                              json={"reason": "bogus_reason", "description": "long enough desc here"},
                              timeout=15)
        assert r_bad.status_code == 422

        # Non-buyer (artist) opening on this order → 403
        r_403 = requests.post(f"{API}/orders/{oid}/dispute", headers=H(a_tok),
                              json={"reason": "damaged", "description": "long enough desc"},
                              timeout=15)
        assert r_403.status_code == 403

        # /disputes/mine as collector includes it
        r_mine_c = requests.get(f"{API}/disputes/mine", headers=H(c_tok), timeout=15)
        assert r_mine_c.status_code == 200
        assert any(x["id"] == did for x in r_mine_c.json())

        # /disputes/mine as artist (seller) includes it
        r_mine_a = requests.get(f"{API}/disputes/mine", headers=H(a_tok), timeout=15)
        assert r_mine_a.status_code == 200
        assert any(x["id"] == did for x in r_mine_a.json())

        # Admin listing
        r_adm = requests.get(f"{API}/admin/disputes?status=open", headers=H(adm_tok), timeout=15)
        assert r_adm.status_code == 200
        assert any(x["id"] == did for x in r_adm.json())

        # non-admin listing → 403
        r_naa = requests.get(f"{API}/admin/disputes", headers=H(c_tok), timeout=15)
        assert r_naa.status_code == 403

        # refund_partial without amount → 400 (must be on OPEN dispute — before reject)
        r_np = requests.post(f"{API}/admin/disputes/{did}/resolve", headers=H(adm_tok),
                             json={"action": "refund_partial", "note": "missing amount"}, timeout=15)
        assert r_np.status_code == 400

        # invalid action → 400
        r_ia = requests.post(f"{API}/admin/disputes/{did}/resolve", headers=H(adm_tok),
                             json={"action": "explode", "note": "nope"}, timeout=15)
        assert r_ia.status_code == 400

        # Resolve with reject
        r_res = requests.post(f"{API}/admin/disputes/{did}/resolve", headers=H(adm_tok),
                              json={"action": "reject", "note": "iter14 test"}, timeout=15)
        assert r_res.status_code == 200, r_res.text
        assert r_res.json()["status"] == "rejected"

        # Order should have dispute_status rejected
        r_o = requests.get(f"{API}/orders/{oid}/dispute", headers=H(c_tok), timeout=15)
        assert r_o.status_code == 200
        assert r_o.json()["status"] == "rejected"

        # Resolving again → 400
        r_again = requests.post(f"{API}/admin/disputes/{did}/resolve", headers=H(adm_tok),
                                json={"action": "reject", "note": "again"}, timeout=15)
        assert r_again.status_code == 400

        # Both parties got notifications
        for who_tok, who in ((c_tok, "buyer"), (a_tok, "seller")):
            r_n = requests.get(f"{API}/notifications", headers=H(who_tok), timeout=15)
            assert r_n.status_code == 200
            notifs = r_n.json()
            kinds = [n.get("kind") for n in notifs]
            assert "dispute_resolved" in kinds, f"{who} missing dispute_resolved"
            # check order enrichment for the resolved notif
            resolved = next(n for n in notifs if n.get("kind") == "dispute_resolved" and n.get("dispute_id") == did)
            assert (resolved.get("order") or {}).get("id") == oid
