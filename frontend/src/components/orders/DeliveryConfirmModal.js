import React, { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api, fileUrl } from "../../api";
import { useAuth } from "../../context/AuthContext";
import { toast } from "sonner";
import { PackageCheck, PackageX, ShieldCheck, Truck, AlertTriangle } from "lucide-react";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));
const POLL_MS = 60000;

export default function DeliveryConfirmModal() {
  const { user } = useAuth();
  const location = useLocation();
  const [pending, setPending] = useState([]);
  const [busy, setBusy] = useState(false);
  const [confirmNo, setConfirmNo] = useState(false);

  const load = useCallback(() => {
    if (!user) { setPending([]); return; }
    api.get("/orders/confirmations/pending").then((r) => setPending(r.data || [])).catch(() => {});
  }, [user]);

  useEffect(() => { load(); }, [load, location.pathname]);
  useEffect(() => {
    if (!user) return;
    const id = setInterval(load, POLL_MS);
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => { clearInterval(id); window.removeEventListener("focus", onFocus); };
  }, [user, load]);

  const order = pending[0];
  useEffect(() => {
    if (!order) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const block = (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); } };
    window.addEventListener("keydown", block, true);
    return () => { document.body.style.overflow = prev; window.removeEventListener("keydown", block, true); };
  }, [order]);

  useEffect(() => { setConfirmNo(false); }, [order?.id]);

  if (!order) return null;

  const answer = async (received) => {
    setBusy(true);
    try {
      await api.post(`/orders/${order.id}/${received ? "confirm-received" : "not-received"}`);
      toast.success(received ? "Thanks — delivery confirmed. The artist's payout is now scheduled." : "Reported. We've frozen the payout and opened a case — our team will review the tracking.");
      window.dispatchEvent(new CustomEvent("order-updated", { detail: { id: order.id } }));
      setPending((p) => p.filter((x) => x.id !== order.id));
    } catch (e) { toast.error(e?.response?.data?.detail || "Something went wrong"); }
    setBusy(false);
  };

  const f = order.fulfillment || {};
  const deadline = f.confirm_deadline ? new Date(f.confirm_deadline) : null;

  return (
    <div data-testid="delivery-confirm-modal" role="dialog" aria-modal="true"
      className="fixed inset-0 z-[5000] bg-[#0A0A0C]/95 backdrop-blur-xl flex items-center justify-center p-4 md:p-8 overflow-y-auto"
      onMouseDown={(e) => e.stopPropagation()}>
      <div className="w-full max-w-lg border border-[#F5A623]/40 bg-[#111113] rounded-sm shadow-[0_0_80px_rgba(245,166,35,0.15)] fade-up">
        <div className="px-6 pt-6 pb-4 border-b border-white/8">
          <div className="label-caps text-[#F5A623] flex items-center gap-2"><ShieldCheck size={12} /> Delivery check · action required</div>
          <h2 className="font-anton text-3xl md:text-4xl uppercase mt-3 leading-none">Did your order arrive?</h2>
          <p className="text-sm text-zinc-400 mt-3 leading-relaxed">
            Tracking shows order <span className="text-white font-semibold">#{order.id.replace(/^order_/, "").slice(0, 8)}</span> was delivered
            {f.carrier_delivered_at && <> on {new Date(f.carrier_delivered_at).toLocaleDateString()}</>}. To protect you and the artist, please confirm before continuing.
            {pending.length > 1 && <span className="text-zinc-500"> ({pending.length} orders waiting)</span>}
          </p>
        </div>

        <div className="px-6 py-4 space-y-3">
          {order.items.map((it, i) => (
            <div key={i} className="flex items-center gap-3" data-testid={`confirm-item-${i}`}>
              {it.image && <img src={resolveImg(it.image)} alt="" className="w-14 h-14 object-cover rounded-sm border border-white/10" />}
              <div className="flex-1 min-w-0">
                <div className="font-unbounded text-sm font-semibold truncate">{it.title}</div>
                <div className="label-caps text-zinc-500 mt-0.5 truncate">by {it.artist_name}</div>
              </div>
              <div className="font-anton text-lg text-[#CCFF00]">${Number(it.price || 0).toLocaleString()}</div>
            </div>
          ))}
          <div className="flex items-center gap-2 text-xs text-zinc-400 bg-white/[0.03] border border-white/8 rounded-sm px-3 py-2" data-testid="confirm-tracking">
            <Truck size={12} className="text-[#7C3AED] shrink-0" />
            <span className="font-mono truncate">{f.carrier} · {f.tracking}</span>
            {f.carrier_delivered_source === "estimated" && <span className="ml-auto label-caps text-zinc-500 shrink-0">est. delivered</span>}
          </div>
        </div>

        {!confirmNo ? (
          <div className="px-6 pb-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button data-testid="confirm-received-btn" disabled={busy} onClick={() => answer(true)}
              className="btn-lime !py-4 !text-xs flex items-center justify-center gap-2">
              <PackageCheck size={16} /> {busy ? "..." : "I received my item"}
            </button>
            <button data-testid="confirm-not-received-btn" disabled={busy} onClick={() => setConfirmNo(true)}
              className="!py-4 text-xs font-semibold uppercase tracking-widest rounded-sm border border-[#FF4D4D]/60 text-[#FF4D4D] hover:bg-[#FF4D4D]/10 transition-colors flex items-center justify-center gap-2">
              <PackageX size={16} /> I did not receive it
            </button>
          </div>
        ) : (
          <div className="px-6 pb-6" data-testid="not-received-confirm-step">
            <div className="border border-[#FF4D4D]/40 bg-[#FF4D4D]/5 rounded-sm p-4 text-sm text-zinc-300 flex gap-3">
              <AlertTriangle size={18} className="text-[#FF4D4D] shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-white">Report this item as not received?</div>
                <div className="text-xs text-zinc-400 mt-1 leading-relaxed">We'll freeze the artist's payout, attach the tracking proof, and open a case for our team to review. False reports may lead to account suspension.</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <button data-testid="not-received-back-btn" disabled={busy} onClick={() => setConfirmNo(false)} className="btn-ghost !py-3 !text-xs">Back</button>
              <button data-testid="not-received-submit-btn" disabled={busy} onClick={() => answer(false)}
                className="!py-3 text-xs font-semibold uppercase tracking-widest rounded-sm bg-[#FF4D4D] text-black hover:bg-[#ff6b6b] transition-colors">
                {busy ? "..." : "Yes, I did not receive it"}
              </button>
            </div>
          </div>
        )}

        <div className="px-6 py-3 border-t border-white/8 text-[11px] text-zinc-500 flex items-center justify-between gap-3">
          <span>This prompt can't be dismissed until you answer.</span>
          {deadline && <span data-testid="confirm-deadline">Auto-confirms {deadline.toLocaleDateString()}</span>}
        </div>
      </div>
    </div>
  );
}
