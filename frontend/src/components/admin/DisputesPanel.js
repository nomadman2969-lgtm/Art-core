import React, { useEffect, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, thumbUrl } from "../../api";
import { REASON_LABELS, DISPUTE_STATUS } from "../orders/OrderExtras";

const resolveImg = (p) => thumbUrl(p, 240);

export function DisputesPanel() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("open");
  const [busy, setBusy] = useState(null);
  const [partial, setPartial] = useState({});
  const [notes, setNotes] = useState({});

  const load = () => api.get("/admin/disputes").then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const resolve = async (d, action) => {
    const amount = action === "refund_partial" ? parseFloat(partial[d.id]) : undefined;
    if (action === "refund_partial" && (!amount || amount <= 0)) return toast.error("Enter a partial amount");
    if (!confirm(action === "reject" ? "Reject this dispute (no refund)?" : `Refund ${action === "refund_full" ? "the full order" : `$${amount}`}?`)) return;
    setBusy(d.id);
    try {
      await api.post(`/admin/disputes/${d.id}/resolve`, { action, amount, note: notes[d.id] || null });
      toast.success(action === "reject" ? "Dispute rejected" : "Refund issued");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(null);
  };

  const shown = items.filter((d) => filter === "all" || (filter === "open" ? ["open", "under_review"].includes(d.status) : !["open", "under_review"].includes(d.status)));

  return (
    <div data-testid="disputes-panel">
      <div className="flex gap-2 mb-6">
        {[["open", "Open"], ["resolved", "Resolved"], ["all", "All"]].map(([k, l]) => (
          <button key={k} data-testid={`disputes-filter-${k}`} onClick={() => setFilter(k)}
            className={`label-caps text-xs px-3 py-2 border rounded-sm ${filter === k ? "border-[#CCFF00] text-[#CCFF00]" : "border-white/10 text-zinc-500"}`}>{l}</button>
        ))}
      </div>
      {shown.length === 0 ? (
        <div className="border border-dashed border-white/10 p-12 text-center label-caps text-zinc-500">No {filter === "all" ? "" : filter} disputes.</div>
      ) : (
        <div className="space-y-4">
          {shown.map((d) => {
            const meta = DISPUTE_STATUS[d.status] || DISPUTE_STATUS.open;
            const openState = ["open", "under_review"].includes(d.status);
            return (
              <div key={d.id} data-testid={`dispute-${d.id}`} className="border border-white/8 rounded-sm p-5">
                <div className="flex flex-wrap items-start gap-4">
                  {d.artwork?.images?.[0] && <img src={resolveImg(d.artwork.images[0])} alt="" className="w-16 h-16 object-cover rounded-sm" />}
                  <div className="flex-1 min-w-[200px]">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-unbounded font-semibold text-sm">{d.artwork?.title || "Order"}</span>
                      <span className="label-caps px-2 py-0.5 rounded-sm text-[10px]" style={{ background: `${meta.color}20`, color: meta.color }}>{meta.label}</span>
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">
                      Order #{d.order_id.slice(0, 8)} · ${Number(d.order?.total || 0).toLocaleString()} · Buyer {d.buyer?.name} · Seller {d.seller?.name || "—"} · {new Date(d.created_at).toLocaleDateString()}
                    </div>
                    <div className="text-sm text-zinc-300 mt-2"><span className="text-[#F5A623] label-caps text-[10px] mr-2">{REASON_LABELS[d.reason]}</span>{d.description}</div>
                    {d.images?.length > 0 && (
                      <div className="flex gap-2 mt-2">{d.images.map((im, i) => <img key={i} src={resolveImg(im)} alt="" className="w-14 h-14 object-cover rounded-sm border border-white/10" />)}</div>
                    )}
                    {!openState && <div className="text-xs text-zinc-500 mt-2">Resolution: {d.resolution}{d.refund_amount ? ` · $${d.refund_amount}` : ""}{d.admin_note ? ` · "${d.admin_note}"` : ""}</div>}
                  </div>
                </div>
                {openState && (
                  <div className="mt-4 pt-4 border-t border-white/8 flex flex-wrap items-center gap-2">
                    <input data-testid={`dispute-note-${d.id}`} placeholder="Note to buyer (optional)" value={notes[d.id] || ""} onChange={(e) => setNotes({ ...notes, [d.id]: e.target.value })}
                      className="flex-1 min-w-[180px] bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 text-xs outline-none focus:border-[#CCFF00]" />
                    <input data-testid={`dispute-partial-${d.id}`} type="number" step="0.01" placeholder="Partial $" value={partial[d.id] || ""} onChange={(e) => setPartial({ ...partial, [d.id]: e.target.value })}
                      className="w-24 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 text-xs outline-none focus:border-[#CCFF00]" />
                    <button data-testid={`dispute-partial-btn-${d.id}`} disabled={busy === d.id} onClick={() => resolve(d, "refund_partial")} className="btn-ghost !py-2 !text-xs">Partial refund</button>
                    <button data-testid={`dispute-full-btn-${d.id}`} disabled={busy === d.id} onClick={() => resolve(d, "refund_full")} className="btn-lime !py-2 !text-xs flex items-center gap-1">
                      {busy === d.id ? <Loader2 size={12} className="animate-spin" /> : <AlertTriangle size={12} />} Full refund
                    </button>
                    <button data-testid={`dispute-reject-btn-${d.id}`} disabled={busy === d.id} onClick={() => resolve(d, "reject")} className="btn-ghost !py-2 !text-xs !text-[#FF4D4D] !border-[#FF4D4D]/40">Reject</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
