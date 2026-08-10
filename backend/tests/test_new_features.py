"""Tests for the 3 new backend areas: Auctions, Rankings, Commissions.

Also includes a light regression sweep against existing endpoints.

Run:
    cd /app && python -m pytest backend/tests/test_new_features.py -v -n 0
"""
import io
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from PIL import Image
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://monster-curated.preview.emergentagent.com").rstrip("/") + "/api"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "house_of_monster"


def _req(method, path, token=None, **kw):
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{BASE}{path}", headers=headers, timeout=30, **kw)


# ---------- module-scoped shared context ----------
@pytest.fixture(scope="module")
def ctx():
    ts = int(time.time())
    uid = uuid.uuid4().hex[:6]

    # admin login
    r = _req("POST", "/auth/login", json={
        "email": "monster@houseofmonster.com", "password": "MonsterAdmin2026!"
    })
    assert r.status_code == 200, r.text
    admin_token = r.json()["token"]

    # ensure upload_fee=0 so artworks go live immediately (simplifies test)
    _req("PATCH", "/admin/settings", token=admin_token, json={"upload_fee": 0})

    # register buyer + 2 artists
    buyer_email = f"TEST_buyer_{ts}_{uid}@test.com"
    artist1_email = f"TEST_artist1_{ts}_{uid}@test.com"
    artist2_email = f"TEST_artist2_{ts}_{uid}@test.com"

    r = _req("POST", "/auth/register", json={
        "email": buyer_email, "password": "Pass1234!", "name": "Buyer T", "role": "buyer"
    })
    assert r.status_code == 200, r.text
    buyer = r.json()

    r = _req("POST", "/auth/register", json={
        "email": artist1_email, "password": "Pass1234!", "name": "Artist One", "role": "artist"
    })
    assert r.status_code == 200, r.text
    artist1 = r.json()

    r = _req("POST", "/auth/register", json={
        "email": artist2_email, "password": "Pass1234!", "name": "Artist Two", "role": "artist"
    })
    assert r.status_code == 200, r.text
    artist2 = r.json()

    # upload an image path (any string works — backend just stores it)
    img = Image.new("RGB", (100, 100), (10, 200, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    r = _req("POST", "/upload/image", token=artist1["token"],
             files={"file": ("t.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 200, r.text
    image_path = r.json()["path"]

    # artist1 creates a LIVE artwork (fee=0)
    r = _req("POST", "/artworks", token=artist1["token"], json={
        "title": "Auction Piece", "description": "d", "price": 500.0,
        "medium": "painting", "images": [image_path],
        "width_in": 24, "height_in": 36, "year": 2026,
    })
    assert r.status_code == 200, r.text
    artwork_live_id = r.json()["id"]
    # fee=0 path: call upload-fee to promote to live
    r = _req("POST", "/payments/upload-fee", token=artist1["token"],
             json={"artwork_id": artwork_live_id, "origin_url": BASE.rsplit("/api", 1)[0]})
    assert r.status_code == 200, r.text
    # verify live
    r = _req("GET", f"/artworks/{artwork_live_id}")
    assert r.status_code == 200 and r.json()["status"] == "live", r.text

    # artist1 creates a PENDING_FEE artwork (temporarily raise fee)
    _req("PATCH", "/admin/settings", token=admin_token, json={"upload_fee": 5.0})
    r = _req("POST", "/artworks", token=artist1["token"], json={
        "title": "Pending Piece", "description": "d", "price": 300.0,
        "medium": "painting", "images": [image_path],
        "width_in": 12, "height_in": 12, "year": 2026,
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_fee"
    artwork_pending_id = r.json()["id"]
    # restore fee=0
    _req("PATCH", "/admin/settings", token=admin_token, json={"upload_fee": 0})

    yield {
        "admin_token": admin_token,
        "buyer": buyer,
        "artist1": artist1,
        "artist2": artist2,
        "artwork_live_id": artwork_live_id,
        "artwork_pending_id": artwork_pending_id,
    }


# ============================================================
# AUCTIONS
# ============================================================
class TestAuctions:
    def test_create_auction_success(self, ctx):
        r = _req("POST", "/auctions", token=ctx["artist1"]["token"], json={
            "artwork_id": ctx["artwork_live_id"],
            "start_price": 100, "reserve_price": 200, "duration_minutes": 60,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "live"
        assert d["seller_id"] == ctx["artist1"]["user"]["id"]
        assert "artwork" in d and d["artwork"]["id"] == ctx["artwork_live_id"]
        assert "seller" in d
        ctx["auction_id"] = d["id"]

    def test_create_auction_on_pending_fee_400(self, ctx):
        r = _req("POST", "/auctions", token=ctx["artist1"]["token"], json={
            "artwork_id": ctx["artwork_pending_id"],
            "start_price": 100, "reserve_price": 0, "duration_minutes": 60,
        })
        assert r.status_code == 400, r.text

    def test_create_auction_not_owner_403(self, ctx):
        r = _req("POST", "/auctions", token=ctx["artist2"]["token"], json={
            "artwork_id": ctx["artwork_live_id"],
            "start_price": 100, "reserve_price": 0, "duration_minutes": 60,
        })
        assert r.status_code == 403, r.text

    def test_create_second_auction_same_artwork_400(self, ctx):
        r = _req("POST", "/auctions", token=ctx["artist1"]["token"], json={
            "artwork_id": ctx["artwork_live_id"],
            "start_price": 100, "reserve_price": 0, "duration_minutes": 60,
        })
        assert r.status_code == 400, r.text

    def test_list_auctions_live(self, ctx):
        r = _req("GET", "/auctions?status=live")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert any(a["id"] == ctx["auction_id"] for a in data)

    def test_get_auction_detail_enriched(self, ctx):
        r = _req("GET", f"/auctions/{ctx['auction_id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == ctx["auction_id"]
        assert "artwork" in d and "seller" in d

    def test_bid_seller_cannot_bid(self, ctx):
        r = _req("POST", f"/auctions/{ctx['auction_id']}/bid",
                 token=ctx["artist1"]["token"], json={"amount": 150})
        assert r.status_code == 400, r.text

    def test_bid_below_start_price_400(self, ctx):
        r = _req("POST", f"/auctions/{ctx['auction_id']}/bid",
                 token=ctx["buyer"]["token"], json={"amount": 50})
        assert r.status_code == 400, r.text

    def test_bid_success_buyer(self, ctx):
        r = _req("POST", f"/auctions/{ctx['auction_id']}/bid",
                 token=ctx["buyer"]["token"], json={"amount": 250})
        assert r.status_code == 200, r.text
        # verify auction state
        r2 = _req("GET", f"/auctions/{ctx['auction_id']}")
        d = r2.json()
        assert d["current_bid"] == 250
        assert d["bid_count"] == 1
        assert d["current_bidder_id"] == ctx["buyer"]["user"]["id"]

    def test_bid_second_bidder_and_outbid_notification(self, ctx):
        # artist2 (acting as buyer role-wise: bid endpoint uses get_current_user, any auth user)
        r = _req("POST", f"/auctions/{ctx['auction_id']}/bid",
                 token=ctx["artist2"]["token"], json={"amount": 300})
        assert r.status_code == 200, r.text
        # check outbid notification for previous bidder (buyer) exists in db
        mc = MongoClient(MONGO_URL)
        try:
            notif = mc[DB_NAME].notifications.find_one({
                "user_id": ctx["buyer"]["user"]["id"],
                "kind": "outbid",
                "auction_id": ctx["auction_id"],
            })
            assert notif is not None, "outbid notification should have been created for previous bidder"
        finally:
            mc.close()

    def test_bid_must_exceed_current_plus_1(self, ctx):
        # current_bid=300, next min = 301
        r = _req("POST", f"/auctions/{ctx['auction_id']}/bid",
                 token=ctx["buyer"]["token"], json={"amount": 300.5})
        assert r.status_code == 400, r.text

    def test_get_bids_history(self, ctx):
        r = _req("GET", f"/auctions/{ctx['auction_id']}/bids")
        assert r.status_code == 200
        bids = r.json()
        assert isinstance(bids, list)
        assert len(bids) >= 2
        # sorted desc by created_at
        assert bids[0]["amount"] == 300

    def test_my_auctions_selling_and_won(self, ctx):
        # seller side
        r = _req("GET", "/auctions/mine", token=ctx["artist1"]["token"])
        assert r.status_code == 200
        data = r.json()
        assert "selling" in data and "won" in data
        assert any(a["id"] == ctx["auction_id"] for a in data["selling"])

    def test_auto_finalize_via_mongo_patch(self, ctx):
        # patch end_at to past and re-fetch
        mc = MongoClient(MONGO_URL)
        try:
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            mc[DB_NAME].auctions.update_one(
                {"id": ctx["auction_id"]}, {"$set": {"end_at": past}}
            )
        finally:
            mc.close()

        r = _req("GET", f"/auctions/{ctx['auction_id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ended", f"expected ended, got {d['status']}"
        # winner_id: current_bid=300 >= reserve=200 → winner is artist2
        assert d["winner_id"] == ctx["artist2"]["user"]["id"]

        # artwork should be marked sold
        r2 = _req("GET", f"/artworks/{ctx['artwork_live_id']}")
        assert r2.status_code == 200
        assert r2.json()["status"] == "sold"

        # notifications auction_won for winner, auction_sold for seller
        mc = MongoClient(MONGO_URL)
        try:
            won_n = mc[DB_NAME].notifications.find_one({
                "user_id": ctx["artist2"]["user"]["id"], "kind": "auction_won",
                "auction_id": ctx["auction_id"],
            })
            sold_n = mc[DB_NAME].notifications.find_one({
                "user_id": ctx["artist1"]["user"]["id"], "kind": "auction_sold",
                "auction_id": ctx["auction_id"],
            })
            assert won_n is not None
            assert sold_n is not None
        finally:
            mc.close()


# ============================================================
# RANKINGS
# ============================================================
class TestRankings:
    def test_get_tiers_ordered(self):
        r = _req("GET", "/rankings/tiers")
        assert r.status_code == 200
        tiers = r.json()
        assert isinstance(tiers, list) and len(tiers) == 6
        names = [t["name"] for t in tiers]
        assert names == ["Legendary", "Diamond", "Platinum", "Gold", "Silver", "Bronze"]

    def test_leaderboard_sorted(self, ctx):
        r = _req("GET", "/rankings/leaderboard")
        assert r.status_code == 200
        lb = r.json()
        assert isinstance(lb, list)
        # sorted desc
        scores = [x["score"] for x in lb]
        assert scores == sorted(scores, reverse=True)
        # our artists present
        ids = {x["id"] for x in lb}
        assert ctx["artist1"]["user"]["id"] in ids
        # breakdown present
        for row in lb:
            assert "tier" in row and "tier_color" in row and "breakdown" in row
            b = row["breakdown"]
            for k in ("sales", "followers", "artworks", "likes_received", "commissions_done"):
                assert k in b

    def test_user_rank(self, ctx):
        r = _req("GET", f"/rankings/{ctx['artist1']['user']['id']}")
        assert r.status_code == 200
        d = r.json()
        assert "score" in d and "tier" in d
        assert d["position"] is not None
        assert d["total_artists"] >= 2

    def test_user_rank_404(self):
        r = _req("GET", "/rankings/nonexistent-id")
        assert r.status_code == 404


# ============================================================
# COMMISSIONS
# ============================================================
class TestCommissions:
    def test_cannot_commission_self(self, ctx):
        r = _req("POST", "/commissions", token=ctx["artist1"]["token"], json={
            "artist_id": ctx["artist1"]["user"]["id"],
            "subject": "self", "budget": 100, "instructions": "n/a",
        })
        assert r.status_code == 400, r.text

    def test_commission_unknown_artist_404(self, ctx):
        r = _req("POST", "/commissions", token=ctx["buyer"]["token"], json={
            "artist_id": "nonexistent",
            "subject": "x", "budget": 50, "instructions": "y",
        })
        assert r.status_code == 404, r.text

    def test_create_commission_success(self, ctx):
        r = _req("POST", "/commissions", token=ctx["buyer"]["token"], json={
            "artist_id": ctx["artist1"]["user"]["id"],
            "subject": "Portrait", "budget": 400,
            "instructions": "please",
            "style": "oil", "size": "24x36",
            "reference_images": ["ref1.jpg"],
        })
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["status"] == "pending"
        assert c["buyer_id"] == ctx["buyer"]["user"]["id"]
        assert c["artist_id"] == ctx["artist1"]["user"]["id"]
        assert c["budget"] == 400
        assert c["reference_images"] == ["ref1.jpg"]
        assert "buyer" in c and "artist" in c
        ctx["commission_id"] = c["id"]

        # notification for artist
        mc = MongoClient(MONGO_URL)
        try:
            n = mc[DB_NAME].notifications.find_one({
                "user_id": ctx["artist1"]["user"]["id"],
                "kind": "commission_request",
                "commission_id": c["id"],
            })
            assert n is not None
        finally:
            mc.close()

    def test_get_commissions_mine_buyer(self, ctx):
        r = _req("GET", "/commissions/mine?as_role=buyer", token=ctx["buyer"]["token"])
        assert r.status_code == 200
        assert any(c["id"] == ctx["commission_id"] for c in r.json())

    def test_get_commissions_mine_artist(self, ctx):
        r = _req("GET", "/commissions/mine?as_role=artist", token=ctx["artist1"]["token"])
        assert r.status_code == 200
        assert any(c["id"] == ctx["commission_id"] for c in r.json())

    def test_get_commission_forbidden_for_third_party(self, ctx):
        r = _req("GET", f"/commissions/{ctx['commission_id']}", token=ctx["artist2"]["token"])
        assert r.status_code == 403, r.text

    def test_get_commission_ok_for_buyer(self, ctx):
        r = _req("GET", f"/commissions/{ctx['commission_id']}", token=ctx["buyer"]["token"])
        assert r.status_code == 200

    def test_respond_counter(self, ctx):
        r = _req("POST", f"/commissions/{ctx['commission_id']}/respond",
                 token=ctx["artist1"]["token"],
                 json={"action": "counter", "counter_amount": 500, "message": "higher"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "counter"
        assert r.json()["counter_amount"] == 500

    def test_respond_twice_400(self, ctx):
        r = _req("POST", f"/commissions/{ctx['commission_id']}/respond",
                 token=ctx["artist1"]["token"],
                 json={"action": "accept"})
        assert r.status_code == 400, r.text

    def test_buyer_accept_counter(self, ctx):
        r = _req("POST", f"/commissions/{ctx['commission_id']}/buyer-action",
                 token=ctx["buyer"]["token"], json={"action": "accept_counter"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "in_progress"
        assert d["budget"] == 500

    def test_progress_by_artist(self, ctx):
        r = _req("POST", f"/commissions/{ctx['commission_id']}/progress",
                 token=ctx["artist1"]["token"],
                 json={"message": "sketch done", "image": "sketch.jpg"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert any(p.get("kind") == "artist_update" for p in d["progress"])
        # notification
        mc = MongoClient(MONGO_URL)
        try:
            n = mc[DB_NAME].notifications.find_one({
                "user_id": ctx["buyer"]["user"]["id"],
                "kind": "commission_progress",
                "commission_id": ctx["commission_id"],
            })
            assert n is not None
        finally:
            mc.close()

    def test_progress_by_non_artist_forbidden(self, ctx):
        r = _req("POST", f"/commissions/{ctx['commission_id']}/progress",
                 token=ctx["buyer"]["token"], json={"message": "x"})
        assert r.status_code == 404, r.text  # code returns 404 when not artist

    def test_deliver_by_artist(self, ctx):
        r = _req("POST", f"/commissions/{ctx['commission_id']}/deliver",
                 token=ctx["artist1"]["token"],
                 json={"final_images": ["final1.jpg", "final2.jpg"], "message": "done"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "delivered"
        assert d["final_images"] == ["final1.jpg", "final2.jpg"]

    def test_progress_not_in_progress_400(self, ctx):
        r = _req("POST", f"/commissions/{ctx['commission_id']}/progress",
                 token=ctx["artist1"]["token"], json={"message": "x"})
        assert r.status_code == 400

    def test_approve_by_buyer(self, ctx):
        r = _req("POST", f"/commissions/{ctx['commission_id']}/approve",
                 token=ctx["buyer"]["token"])
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved"

    def test_cancel_after_approved_400(self, ctx):
        r = _req("POST", f"/commissions/{ctx['commission_id']}/buyer-action",
                 token=ctx["buyer"]["token"], json={"action": "cancel"})
        assert r.status_code == 400


# ============================================================
# LIGHT REGRESSION
# ============================================================
class TestRegression:
    def test_root(self):
        r = _req("GET", "/")
        assert r.status_code == 200 and r.json().get("status") == "ok"

    def test_settings(self):
        r = _req("GET", "/settings")
        assert r.status_code == 200 and "commission_percent" in r.json()

    def test_admin_login(self):
        r = _req("POST", "/auth/login", json={
            "email": "monster@houseofmonster.com", "password": "MonsterAdmin2026!"
        })
        assert r.status_code == 200 and r.json()["user"]["role"] == "admin"

    def test_artworks_list(self):
        r = _req("GET", "/artworks")
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_feed_public(self):
        r = _req("GET", "/feed")
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_search_unified(self):
        r = _req("GET", "/search?q=a")
        assert r.status_code == 200

    def test_admin_stats(self, ctx):
        r = _req("GET", "/admin/stats", token=ctx["admin_token"])
        assert r.status_code == 200

    def test_artist_dashboard(self, ctx):
        r = _req("GET", "/artist/dashboard", token=ctx["artist1"]["token"])
        assert r.status_code == 200
