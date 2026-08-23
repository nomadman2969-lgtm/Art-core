import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fileUrl } from "../api";
import { toast } from "sonner";
import { Package, Star, Download } from "lucide-react";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export function Orders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.get("/orders/mine").then((r) => setOrders(r.data)).finally(() => setLoading(false));
  }, []);
  return (
    <div data-testid="orders-page" className="max-w-3xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]"><Package size={12} className="inline mr-2" /> Order History</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4 mb-10">Your Orders</h1>
      {loading ? <div className="text-zinc-500 py-16 text-center label-caps">Loading...</div> :
        orders.length === 0 ? (
          <div className="border border-dashed border-white/10 py-20 text-center rounded-sm">
            <div className="label-caps text-zinc-500">No orders yet.</div>
            <Link to="/marketplace" className="btn-lime mt-6 inline-flex">Browse Marketplace</Link>
          </div>
        ) : (
          <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
            {orders.map((o) => (
              <Link key={o.id} to={`/orders/${o.id}`} data-testid={`order-${o.id}`}
                className="p-4 flex flex-wrap items-center gap-4 hover:bg-white/[0.03] transition-colors">
                <div className="flex -space-x-3">
                  {o.items.slice(0, 3).map((it, i) => (
                    <img key={i} src={resolveImg(it.artwork?.images?.[0])} className="w-14 h-14 object-cover border-2 border-[#0A0A0C] rounded-sm" alt="" />
                  ))}
                </div>
                <div className="flex-1 min-w-[180px]">
                  <div className="font-unbounded font-semibold">Order #{o.id.slice(0, 8)}</div>
                  <div className="label-caps mt-1">{new Date(o.created_at).toLocaleDateString()} · {o.items.length} piece(s)</div>
                </div>
                <div className="font-anton text-2xl text-[#CCFF00]">${Number(o.total).toLocaleString()}</div>
              </Link>
            ))}
          </div>
        )}
    </div>
  );
}

export function OrderDetail() {
  const { id } = useParams();
  const [o, setO] = useState(null);
  const [reviewFor, setReviewFor] = useState(null);
  const [rating, setRating] = useState(5);
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);
  const [reviewed, setReviewed] = useState({}); // artwork_id -> true

  const load = async () => {
    try {
      const r = await api.get(`/orders/${id}`);
      setO(r.data);
      // Check which items already have a review by me
      const status = {};
      await Promise.all(r.data.items.map(async (it) => {
        try {
          const rr = await api.get(`/artworks/${it.artwork_id}/reviews`);
          const mine = rr.data.find((rev) => rev.order_id === id);
          if (mine) status[it.artwork_id] = true;
        } catch {}
      }));
      setReviewed(status);
    } catch { toast.error("Order not found"); }
  };
  useEffect(() => { load(); }, [id]);

  const submitReview = async () => {
    setPosting(true);
    try {
      await api.post("/reviews", { order_id: id, artwork_id: reviewFor, rating, text });
      toast.success("Review posted");
      setReviewFor(null); setText(""); setRating(5);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setPosting(false);
  };

  if (!o) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;

  return (
    <div data-testid="order-detail" className="max-w-3xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <Link to="/orders" className="label-caps text-zinc-500 hover:text-[#CCFF00]">← All orders</Link>
      <div className="mt-6 mb-8">
        <div className="label-caps text-[#CCFF00]">Order #{o.id.slice(0, 8)}</div>
        <h1 className="font-anton text-4xl md:text-6xl uppercase mt-3">Receipt</h1>
        <div className="label-caps text-zinc-500 mt-2">Placed {new Date(o.created_at).toLocaleString()}</div>
      </div>

      <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
        {o.items.map((it, i) => (
          <div key={i} data-testid={`receipt-item-${i}`} className="p-4 flex flex-wrap items-center gap-4">
            <img src={resolveImg(it.artwork?.images?.[0])} className="w-20 h-20 object-cover rounded-sm" alt="" />
            <div className="flex-1 min-w-[160px]">
              <div className="font-unbounded font-semibold">{it.artwork?.title}</div>
              <div className="label-caps mt-1">by {it.artist_name} · Qty {it.quantity}</div>
            </div>
            <div className="font-anton text-xl text-[#CCFF00]">${Number(it.price).toLocaleString()}</div>
            {reviewed[it.artwork_id] ? (
              <div className="badge-lime">Reviewed</div>
            ) : (
              <button data-testid={`review-btn-${i}`} onClick={() => setReviewFor(it.artwork_id)} className="btn-ghost !py-2 !text-xs"><Star size={12} className="mr-1" /> Review</button>
            )}
          </div>
        ))}
      </div>
      <div className="mt-6 border border-white/8 p-6 rounded-sm">
        <div className="flex justify-between label-caps"><span>Subtotal</span><span>${o.total.toFixed(2)}</span></div>
        <div className="flex justify-between font-anton text-2xl mt-3 pt-3 border-t border-white/8">
          <span>Total</span><span className="text-[#CCFF00]">${o.total.toFixed(2)}</span>
        </div>
        <div className="label-caps text-zinc-500 mt-4">Shipping coordinated by Art Core.</div>
      </div>

      {reviewFor && (
        <div className="mt-8 glass-card p-6 rounded-sm" data-testid="review-panel">
          <div className="label-caps text-[#CCFF00] mb-4">Write a review</div>
          <div className="flex gap-1 mb-4">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} data-testid={`star-${n}`} onClick={() => setRating(n)}>
                <Star size={22} fill={n <= rating ? "#CCFF00" : "none"} color={n <= rating ? "#CCFF00" : "#52525B"} />
              </button>
            ))}
          </div>
          <textarea data-testid="review-text" value={text} onChange={(e) => setText(e.target.value)} rows={4}
            placeholder="How was the piece? How was the seller?"
            className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none focus:border-[#CCFF00]" />
          <div className="flex gap-3 mt-4">
            <button data-testid="review-submit" disabled={posting || !text.trim()} onClick={submitReview} className="btn-lime">{posting ? "Posting..." : "Post Review"}</button>
            <button onClick={() => setReviewFor(null)} className="btn-ghost">Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
