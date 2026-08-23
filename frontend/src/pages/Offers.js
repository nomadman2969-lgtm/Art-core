import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl, ORIGIN } from "../api";
import { toast } from "sonner";
import { Tag, CreditCard, Check, X, ArrowRight } from "lucide-react";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

const STATUS = {
  pending: { label: "Pending", color: "#F5A623" },
  countered: { label: "Countered", color: "#7C3AED" },
  accepted: { label: "Accepted — Pay now", color: "#CCFF00" },
  paid: { label: "Paid", color: "#CCFF00" },
  declined: { label: "Declined", color: "#FF4D4D" },
  withdrawn: { label: "Withdrawn", color: "#71717A" },
  expired: { label: "Expired", color: "#71717A" },
};

export default function OffersInbox() {
  const [asRole, setAsRole] = useState("buyer");
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get(`/offers/mine?as_role=${asRole}`).then((r) => setOffers(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, [asRole]);

  return (
    <div data-testid="offers-inbox" className="max-w-4xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]"><Tag size={12} className="inline mr-2" /> Offers</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4 mb-8">Make a Deal</h1>
      <div className="flex gap-1 border-b border-white/8 mb-8">
        {[["buyer", "As Buyer"], ["seller", "As Artist"]].map(([k, l]) => (
          <button key={k} data-testid={`offers-tab-${k}`} onClick={() => setAsRole(k)}
            className={`label-caps px-4 py-3 border-b-2 ${asRole === k ? "border-[#CCFF00] text-white" : "border-transparent text-zinc-500"}`}>{l}</button>
        ))}
      </div>
      {loading ? <div className="text-zinc-500 py-16 text-center label-caps">Loading...</div> :
        offers.length === 0 ? (
          <div className="border border-dashed border-white/10 py-20 text-center rounded-sm">
            <div className="label-caps text-zinc-500">No offers yet.</div>
            <div className="text-sm text-zinc-400 mt-2">
              {asRole === "buyer" ? <>Explore the <Link to="/marketplace" className="text-[#CCFF00]">marketplace</Link> and click "Make an Offer" on any piece.</>
                : "Buyers can send offers on your live artworks. They'll appear here."}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {offers.map((o) => <OfferRow key={o.id} o={o} asRole={asRole} reload={load} />)}
          </div>
        )}
    </div>
  );
}

function OfferRow({ o, asRole, reload }) {
  const [counter, setCounter] = useState("");
  const [showCounter, setShowCounter] = useState(false);
  const [busy, setBusy] = useState(false);
  const meta = STATUS[o.status] || { label: o.status, color: "#71717A" };

  const respond = async (action, extra = {}) => {
    setBusy(true);
    try {
      await api.post(`/offers/${o.id}/respond`, { action, ...extra });
      toast.success("Sent");
      setShowCounter(false);
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };
  const buyerAct = async (action) => {
    setBusy(true);
    try {
      await api.post(`/offers/${o.id}/buyer-action`, { action });
      toast.success("Done");
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };
  const pay = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/payments/offers/${o.id}/pay`, { origin_url: ORIGIN });
      window.location.href = r.data.checkout_url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Payment failed"); setBusy(false); }
  };

  const displayAmount = o.status === "countered" ? o.counter_amount : o.amount;

  return (
    <div data-testid={`offer-${o.id}`} className="border border-white/8 rounded-sm p-4 md:p-5 bg-[#121214]">
      <div className="flex flex-wrap items-start gap-4">
        <img src={resolveImg(o.artwork?.images?.[0])} className="w-24 h-24 md:w-28 md:h-28 object-cover rounded-sm" alt="" />
        <div className="flex-1 min-w-[180px]">
          <Link to={`/artwork/${o.artwork?.id}`} className="font-unbounded font-semibold hover:text-[#CCFF00]">{o.artwork?.title}</Link>
          <div className="text-xs text-zinc-500 mt-1">
            {asRole === "buyer" ? <>to {o.artist?.name}</> : <>from {o.buyer?.name}</>} · list ${Number(o.list_price).toLocaleString()}
          </div>
          <div className="mt-3 flex items-baseline gap-3 flex-wrap">
            <div className="font-anton text-2xl" style={{ color: meta.color }}>${Number(displayAmount).toLocaleString()}</div>
            <div className="label-caps px-2 py-1 rounded-sm" style={{ background: `${meta.color}20`, color: meta.color }}>{meta.label}</div>
          </div>
          {o.message && <div className="text-xs text-zinc-400 mt-3 italic">"{o.message}"</div>}
        </div>
      </div>

      {/* Actions */}
      <div className="mt-4 pt-4 border-t border-white/8 flex flex-wrap gap-2">
        {asRole === "seller" && o.status === "pending" && (
          <>
            <button data-testid={`offer-accept-${o.id}`} disabled={busy} onClick={() => respond("accept")} className="btn-lime !py-2 !text-xs"><Check size={12} className="mr-1" /> Accept ${Number(o.amount).toLocaleString()}</button>
            <button data-testid={`offer-counter-${o.id}`} disabled={busy} onClick={() => setShowCounter(!showCounter)} className="btn-violet !py-2 !text-xs">Counter</button>
            <button data-testid={`offer-decline-${o.id}`} disabled={busy} onClick={() => respond("decline")} className="btn-ghost !py-2 !text-xs"><X size={12} className="mr-1" /> Decline</button>
          </>
        )}
        {asRole === "seller" && showCounter && o.status === "pending" && (
          <div className="w-full mt-2 flex gap-2">
            <input data-testid={`offer-counter-input-${o.id}`} type="number" step="1" min={o.amount + 1} max={o.list_price} placeholder={`> $${o.amount} and ≤ $${o.list_price}`}
              value={counter} onChange={(e) => setCounter(e.target.value)}
              className="flex-1 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#7C3AED]" />
            <button data-testid={`offer-counter-send-${o.id}`} disabled={busy || !counter} onClick={() => respond("counter", { counter_amount: Number(counter) })} className="btn-violet !py-2 !text-xs">Send Counter</button>
          </div>
        )}
        {asRole === "buyer" && o.status === "countered" && (
          <>
            <button data-testid={`accept-counter-${o.id}`} disabled={busy} onClick={() => buyerAct("accept_counter")} className="btn-lime !py-2 !text-xs">Accept ${Number(o.counter_amount).toLocaleString()}</button>
            <button data-testid={`decline-counter-${o.id}`} disabled={busy} onClick={() => buyerAct("decline_counter")} className="btn-ghost !py-2 !text-xs">Decline</button>
          </>
        )}
        {asRole === "buyer" && (o.status === "pending" || o.status === "countered") && (
          <button data-testid={`withdraw-${o.id}`} disabled={busy} onClick={() => buyerAct("withdraw")} className="btn-ghost !py-2 !text-xs">Withdraw</button>
        )}
        {asRole === "buyer" && o.status === "accepted" && (
          <button data-testid={`pay-offer-${o.id}`} disabled={busy} onClick={pay} className="btn-lime !py-2 !text-xs">
            <CreditCard size={12} className="mr-1" /> Pay ${Number(o.amount).toLocaleString()}
          </button>
        )}
        {o.status === "paid" && (
          <Link to="/orders" className="btn-ghost !py-2 !text-xs"><ArrowRight size={12} className="mr-1" /> View Order</Link>
        )}
      </div>
    </div>
  );
}
