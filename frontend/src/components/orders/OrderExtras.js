import React, { useEffect, useState } from "react";
import { Award, AlertTriangle, Loader2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../api";

export const REASON_LABELS = { damaged: "Arrived damaged", not_received: "Never arrived", not_as_described: "Not as described", other: "Something else" };
export const DISPUTE_STATUS = {
  open: { label: "Dispute open", color: "#F5A623" },
  under_review: { label: "Under review", color: "#F5A623" },
  refunded: { label: "Resolved · refunded", color: "#CCFF00" },
  rejected: { label: "Resolved · no refund", color: "#FF4D4D" },
};

export function CertificateButton({ orderId, artworkId, index }) {
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      const r = await api.get(`/orders/${orderId}/certificate/${artworkId}`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `ArtCore_Certificate_${artworkId.slice(0, 6)}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast.error(e?.response?.status === 400 ? "Certificate void (refunded order)" : "Couldn't generate certificate"); }
    setBusy(false);
  };
  return (
    <button data-testid={`coa-btn-${index}`} onClick={download} disabled={busy}
      className="btn-ghost !py-2 !text-xs !border-[#CCFF00]/40 !text-[#CCFF00] flex items-center gap-1">
      {busy ? <Loader2 size={12} className="animate-spin" /> : <Award size={12} />} Certificate
    </button>
  );
}

export function DisputePanel({ order, isBuyer, onChanged }) {
  const [dispute, setDispute] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ reason: "damaged", description: "", images: [] });
  const [busy, setBusy] = useState(false);

  const load = () => api.get(`/orders/${order.id}/dispute`).then((r) => setDispute(r.data)).catch(() => setDispute(null));
  useEffect(() => { load(); }, [order.id]);

  const upload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    try {
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setForm((x) => ({ ...x, images: [...x.images, r.data.path] }));
    } catch { toast.error("Upload failed"); }
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post(`/orders/${order.id}/dispute`, form);
      toast.success("Dispute opened — our team will review it");
      setOpen(false); load(); onChanged?.();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const resolved = dispute && ["refunded", "rejected"].includes(dispute.status);
  const canOpen = isBuyer && !order.refunded && (!dispute || resolved);
  if (!dispute && !canOpen) return null;
  const meta = dispute ? (DISPUTE_STATUS[dispute.status] || DISPUTE_STATUS.open) : null;

  return (
    <div className="mt-6 border border-white/8 rounded-sm p-5" data-testid="dispute-panel">
      {dispute && !open ? (
        <>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="label-caps flex items-center gap-2"><AlertTriangle size={12} /> Problem report</div>
            <div data-testid="dispute-status" className="label-caps px-2 py-1 rounded-sm" style={{ background: `${meta.color}20`, color: meta.color }}>{meta.label}</div>
          </div>
          <div className="text-sm text-zinc-300 mt-3"><span className="text-zinc-500">{REASON_LABELS[dispute.reason]} — </span>{dispute.description}</div>
          {dispute.refund_amount != null && <div className="font-anton text-xl text-[#CCFF00] mt-2">Refunded ${Number(dispute.refund_amount).toLocaleString()}</div>}
          {dispute.admin_note && <div className="text-xs text-zinc-400 mt-2 border-l-2 border-white/10 pl-3">Team note: {dispute.admin_note}</div>}
          <div className="text-[11px] text-zinc-600 mt-2">Opened {new Date(dispute.created_at).toLocaleString()}</div>
          {canOpen && (
            <button data-testid="open-dispute-btn" onClick={() => setOpen(true)} className="btn-ghost !py-2 !text-xs mt-3 !text-[#FF4D4D] !border-[#FF4D4D]/40 flex items-center gap-1">
              <AlertTriangle size={12} /> Report another problem
            </button>
          )}
        </>
      ) : !open ? (
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="text-xs text-zinc-400">Damaged, missing, or not what you expected? Buyer protection covers you.</div>
          <button data-testid="open-dispute-btn" onClick={() => setOpen(true)} className="btn-ghost !py-2 !text-xs !text-[#FF4D4D] !border-[#FF4D4D]/40 flex items-center gap-1">
            <AlertTriangle size={12} /> Report a problem
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3" data-testid="dispute-form">
          <div className="flex items-center justify-between"><div className="label-caps text-[#FF4D4D]">Report a problem</div>
            <button type="button" onClick={() => setOpen(false)} className="text-zinc-500"><X size={14} /></button></div>
          <select data-testid="dispute-reason" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}
            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 text-sm outline-none focus:border-[#FF4D4D]">
            {Object.entries(REASON_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <textarea data-testid="dispute-description" required minLength={10} rows={4} value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Tell us what happened (at least 10 characters)…"
            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 text-sm outline-none focus:border-[#FF4D4D]" />
          <div className="flex items-center gap-3 flex-wrap">
            <label className="btn-ghost !py-2 !text-xs cursor-pointer flex items-center gap-1"><Upload size={12} /> Add photo
              <input data-testid="dispute-photo" type="file" accept="image/*" className="hidden" onChange={upload} /></label>
            {form.images.length > 0 && <span className="text-xs text-zinc-400">{form.images.length} photo{form.images.length > 1 ? "s" : ""} attached</span>}
          </div>
          <button data-testid="dispute-submit" disabled={busy || form.description.trim().length < 10}
            className="btn-lime !py-2.5 !text-xs w-full flex items-center justify-center gap-2">
            {busy ? <Loader2 size={12} className="animate-spin" /> : <AlertTriangle size={12} />} Submit report
          </button>
        </form>
      )}
    </div>
  );
}
