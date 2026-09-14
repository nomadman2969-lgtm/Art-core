import { useTranslation } from "react-i18next";
import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fileUrl } from "../api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Package, Star, Download, Truck, CheckCircle2, PackageCheck, PackageX, ShieldCheck } from "lucide-react";
import { CertificateButton, DisputePanel } from "../components/orders/OrderExtras";
import { LiveTrackingPanel } from "../components/orders/LiveTrackingPanel";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

const FULFILLMENT_META = {
  pending: { label: "Awaiting Shipment", color: "#F5A623" },
  shipped: { label: "Shipped", color: "#7C3AED" },
  carrier_delivered: { label: "Delivered — awaiting buyer confirmation", color: "#F5A623" },
  delivered: { label: "Delivered", color: "#CCFF00" },
  not_received: { label: "Not received — under review", color: "#FF4D4D" },
};

export function Orders() {
  const { t } = useTranslation();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.get("/orders/mine").then((r) => setOrders(r.data)).finally(() => setLoading(false));
  }, []);
  return (
    <div data-testid="orders-page" className="max-w-3xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]"><Package size={12} className="inline mr-2" /> {t("orders.kicker")}</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4 mb-10">{t("orders.title")}</h1>
      {loading ? <div className="text-zinc-500 py-16 text-center label-caps">{t("common.loading")}</div> :
        orders.length === 0 ? (
          <div className="border border-dashed border-white/10 py-20 text-center rounded-sm">
            <div className="label-caps text-zinc-500">{t("orders.empty")}</div>
            <Link to="/marketplace" className="btn-lime mt-6 inline-flex">Browse Marketplace</Link>
          </div>
        ) : (
          <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
            {orders.map((o) => {
              const fm = FULFILLMENT_META[(o.fulfillment || {}).status || "pending"] || FULFILLMENT_META.pending;
              return (
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
                    <div className="label-caps mt-1 inline-block px-2 py-0.5 rounded-sm" style={{ background: `${fm.color}20`, color: fm.color }}>{fm.label}</div>
                  </div>
                  <div className="font-anton text-2xl text-[#CCFF00]">${Number(o.total).toLocaleString()}</div>
                </Link>
              );
            })}
          </div>
        )}
    </div>
  );
}

export function SellingOrders() {
  const { t } = useTranslation();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.get("/orders/selling").then((r) => setOrders(r.data)).finally(() => setLoading(false));
  }, []);
  return (
    <div data-testid="selling-orders-page" className="max-w-3xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#7C3AED]"><Package size={12} className="inline mr-2" /> {t("orders.selling_kicker")}</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4 mb-10">{t("orders.selling_title")}</h1>
      {loading ? <div className="text-zinc-500 py-16 text-center label-caps">{t("common.loading")}</div> :
        orders.length === 0 ? (
          <div className="border border-dashed border-white/10 py-20 text-center rounded-sm">
            <div className="label-caps text-zinc-500">No sales yet.</div>
          </div>
        ) : (
          <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
            {orders.map((o) => {
              const fm = FULFILLMENT_META[(o.fulfillment || {}).status || "pending"] || FULFILLMENT_META.pending;
              return (
                <Link key={o.id} to={`/orders/${o.id}`} data-testid={`selling-${o.id}`}
                  className="p-4 flex flex-wrap items-center gap-4 hover:bg-white/[0.03] transition-colors">
                  <img src={resolveImg(o.items[0]?.artwork?.images?.[0])} className="w-14 h-14 object-cover rounded-sm" alt="" />
                  <div className="flex-1 min-w-[180px]">
                    <div className="font-unbounded font-semibold">Order #{o.id.slice(0, 8)}</div>
                    <div className="label-caps mt-1">{new Date(o.created_at).toLocaleDateString()}</div>
                    <div className="label-caps mt-1 inline-block px-2 py-0.5 rounded-sm" style={{ background: `${fm.color}20`, color: fm.color }}>{fm.label}</div>
                  </div>
                  <div className="font-anton text-2xl text-[#CCFF00]">${Number(o.total).toLocaleString()}</div>
                </Link>
              );
            })}
          </div>
        )}
    </div>
  );
}

export function OrderDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [o, setO] = useState(null);
  const [reviewFor, setReviewFor] = useState(null);
  const [rating, setRating] = useState(5);
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);
  const [reviewed, setReviewed] = useState({}); // artwork_id -> true
  const [shipForm, setShipForm] = useState({ carrier: "USPS", tracking: "", note: "" });
  const [shipBusy, setShipBusy] = useState(false);

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
  useEffect(() => {
    const h = (e) => { if (e.detail?.id === id) load(); };
    window.addEventListener("order-updated", h);
    return () => window.removeEventListener("order-updated", h);
  }, [id]);

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

  const submitShip = async (e) => {
    e.preventDefault();
    setShipBusy(true);
    try {
      await api.post(`/orders/${id}/ship`, shipForm);
      toast.success("Marked shipped");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setShipBusy(false);
  };

  const markDelivered = async () => {
    setShipBusy(true);
    try {
      await api.post(`/orders/${id}/confirm-received`);
      toast.success("Delivery confirmed — payout scheduled");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setShipBusy(false);
  };

  const notReceived = async () => {
    if (!window.confirm("Report this item as not received? We'll freeze the artist's payout and open a case with the tracking proof attached.")) return;
    setShipBusy(true);
    try {
      await api.post(`/orders/${id}/not-received`);
      toast.success("Reported — payout frozen, case opened");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setShipBusy(false);
  };

  const carrierDelivered = async () => {
    setShipBusy(true);
    try {
      await api.post(`/orders/${id}/carrier-delivered`);
      toast.success("Buyer asked to confirm delivery");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setShipBusy(false);
  };

  if (!o) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;

  const isBuyer = user?.id === o.buyer_id;
  const isSeller = (o.artist_payouts || []).some((p) => p.artist_id === user?.id);
  const fulfill = o.fulfillment || { status: "pending" };
  const fm = FULFILLMENT_META[fulfill.status] || FULFILLMENT_META.pending;

  return (
    <div data-testid="order-detail" className="max-w-3xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <Link to={isSeller && !isBuyer ? "/selling" : "/orders"} className="label-caps text-zinc-500 hover:text-[#CCFF00]">← All orders</Link>
      <div className="mt-6 mb-8">
        <div className="label-caps text-[#CCFF00]">Order #{o.id.slice(0, 8)}</div>
        <h1 className="font-anton text-4xl md:text-6xl uppercase mt-3">Receipt</h1>
        <div className="label-caps text-zinc-500 mt-2">Placed {new Date(o.created_at).toLocaleString()}</div>
      </div>

      {/* Fulfillment status */}
      <div className="mb-6 glass-card p-5 rounded-sm" data-testid="fulfillment-panel">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="label-caps flex items-center gap-2"><Truck size={12} /> Fulfillment</div>
            <div className="mt-2 label-caps px-2 py-1 rounded-sm inline-block" style={{ background: `${fm.color}20`, color: fm.color }}>{fm.label}</div>
          </div>
          {fulfill.tracking && (
            <div className="text-right">
              <div className="label-caps">Tracking</div>
              <div className="font-unbounded text-sm mt-1">{fulfill.carrier} · {fulfill.tracking}</div>
              {fulfill.shipped_at && <div className="text-xs text-zinc-500 mt-1">Shipped {new Date(fulfill.shipped_at).toLocaleDateString()}</div>}
            </div>
          )}
        </div>
        {(isBuyer || isSeller) && <LiveTrackingPanel orderId={o.id} fulfillment={fulfill} />}
        {isSeller && fulfill.status === "pending" && (
          <form onSubmit={submitShip} className="mt-4 pt-4 border-t border-white/8 space-y-3" data-testid="ship-form">
            <div className="text-[11px] text-zinc-500" data-testid="tracking-required-note">Tracking is required — you can't mark an order shipped without it. When tracking shows delivered, the collector must confirm receipt (or report it missing); your payout releases 2 days after confirmation, or 10 business days after the sale if they never answer.</div>
            <div className="grid md:grid-cols-2 gap-3">
              <input required placeholder="Carrier (USPS, UPS...)" value={shipForm.carrier}
                data-testid="ship-carrier"
                onChange={(e) => setShipForm({ ...shipForm, carrier: e.target.value })}
                className="bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#7C3AED]" />
              <input required placeholder="Tracking number" value={shipForm.tracking}
                data-testid="ship-tracking"
                onChange={(e) => setShipForm({ ...shipForm, tracking: e.target.value })}
                className="bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#7C3AED]" />
            </div>
            <input placeholder="Note to buyer (optional)" value={shipForm.note}
              onChange={(e) => setShipForm({ ...shipForm, note: e.target.value })}
              className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#7C3AED]" />
            <button data-testid="ship-submit" disabled={shipBusy} className="btn-violet !py-2 !text-xs">
              <Truck size={12} className="mr-2" />{shipBusy ? "Sending..." : "Mark Shipped"}
            </button>
          </form>
        )}
        {isSeller && fulfill.status === "shipped" && (
          <div className="mt-4 pt-4 border-t border-white/8" data-testid="seller-shipped-panel">
            <button data-testid="carrier-delivered-btn" disabled={shipBusy} onClick={carrierDelivered} className="btn-violet !py-2 !text-xs">
              <PackageCheck size={12} className="mr-2" />{shipBusy ? "..." : "Tracking shows delivered"}
            </button>
            <div className="text-xs text-zinc-500 mt-2">{fulfill.tracker_id ? "Live tracking is on — this flips automatically when the carrier reports delivered. Use this button only if the carrier site shows delivered but we haven't caught up." : "Once tracking says delivered, tap this — the collector is prompted to confirm receipt. If they don't answer within 3 days, delivery is confirmed automatically. (Also auto-flagged 7 days after shipping.)"}</div>
          </div>
        )}
        {isBuyer && ["shipped", "carrier_delivered"].includes(fulfill.status) && (
          <div className="mt-4 pt-4 border-t border-white/8" data-testid="buyer-confirm-panel">
            {fulfill.status === "carrier_delivered" && (
              <div className="text-xs text-[#F5A623] mb-3 flex items-center gap-2" data-testid="carrier-delivered-note">
                <ShieldCheck size={12} /> Tracking shows delivered{fulfill.carrier_delivered_at ? ` on ${new Date(fulfill.carrier_delivered_at).toLocaleDateString()}` : ""}. Please confirm.
                {fulfill.confirm_deadline && <span className="text-zinc-500">Auto-confirms {new Date(fulfill.confirm_deadline).toLocaleDateString()}.</span>}
              </div>
            )}
            <div className="flex flex-wrap gap-3">
              <button data-testid="mark-delivered-btn" disabled={shipBusy} onClick={markDelivered} className="btn-lime !py-2 !text-xs">
                <CheckCircle2 size={12} className="mr-2" />{shipBusy ? "..." : "I received my item"}
              </button>
              <button data-testid="not-received-btn" disabled={shipBusy} onClick={notReceived}
                className="!py-2 px-4 text-xs font-semibold uppercase tracking-widest rounded-sm border border-[#FF4D4D]/60 text-[#FF4D4D] hover:bg-[#FF4D4D]/10 transition-colors inline-flex items-center">
                <PackageX size={12} className="mr-2" /> I did not receive it
              </button>
            </div>
            <div className="text-xs text-zinc-500 mt-2">Confirming receipt schedules the artist payout. Reporting not-received freezes it and opens a case.</div>
          </div>
        )}
        {isSeller && fulfill.status === "carrier_delivered" && (
          <div className="text-xs text-[#F5A623] mt-3" data-testid="seller-awaiting-note">Waiting for the collector to confirm receipt{fulfill.confirm_deadline ? ` — auto-confirms ${new Date(fulfill.confirm_deadline).toLocaleDateString()}` : ""}.</div>
        )}
        {fulfill.status === "not_received" && (
          <div className="text-xs text-[#FF4D4D] mt-3" data-testid="not-received-note">Collector reported this item as not received. Payout is frozen while Art Core reviews the tracking proof.</div>
        )}
        {fulfill.status === "delivered" && (
          <div className="text-xs text-zinc-500 mt-3">Delivered {fulfill.delivered_at ? new Date(fulfill.delivered_at).toLocaleDateString() : ""}{fulfill.confirmed_how === "auto" ? " (auto-confirmed)" : ""}. Payout scheduled.</div>
        )}
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
            {(isBuyer || isSeller) && !o.refunded && <CertificateButton orderId={o.id} artworkId={it.artwork_id} index={i} />}
            {isBuyer && fulfill.status === "delivered" && (
              reviewed[it.artwork_id] ? (
                <div className="badge-lime">Reviewed</div>
              ) : (
                <button data-testid={`review-btn-${i}`} onClick={() => setReviewFor(it.artwork_id)} className="btn-ghost !py-2 !text-xs"><Star size={12} className="mr-1" /> Review</button>
              )
            )}
          </div>
        ))}
      </div>
      <div className="mt-6 border border-white/8 p-6 rounded-sm">
        <div className="flex justify-between label-caps"><span>Subtotal</span><span>${o.total.toFixed(2)}</span></div>
        <div className="flex justify-between font-anton text-2xl mt-3 pt-3 border-t border-white/8">
          <span>Total</span><span className="text-[#CCFF00]">${o.total.toFixed(2)}</span>
        </div>
        <div className="label-caps text-zinc-500 mt-4">
          {isBuyer && fulfill.status !== "delivered" && "You can leave a review once the piece is confirmed delivered."}
        </div>
      </div>

      <DisputePanel order={o} isBuyer={isBuyer} onChanged={load} />

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
