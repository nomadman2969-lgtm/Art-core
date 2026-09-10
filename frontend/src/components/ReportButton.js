import React, { useState } from "react";
import { Flag, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";

export const REPORT_REASONS = {
  spam: "Spam or misleading", stolen_art: "Stolen / not their artwork", inappropriate: "Inappropriate content",
  harassment: "Harassment or hate", scam: "Scam or fraud", copyright: "Copyright violation", other: "Something else",
};

export function ReportButton({ targetType, targetId, ownerId, compact = false, className = "" }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("spam");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  if (!user || (ownerId && ownerId === user.id)) return null;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/reports", { target_type: targetType, target_id: targetId, reason, details: details || null });
      toast.success("Thanks — our team will review this");
      setOpen(false); setDetails("");
    } catch (er) { toast.error(er?.response?.data?.detail || "Couldn't send report"); }
    setBusy(false);
  };

  return (
    <>
      <button data-testid={`report-btn-${targetType}`} onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(true); }} title="Report"
        className={compact ? `p-1.5 rounded-sm text-zinc-500 hover:text-[#FF4D4D] hover:bg-white/5 ${className}` : `btn-ghost !py-1.5 !px-2.5 !text-xs flex items-center gap-1 hover:!text-[#FF4D4D] ${className}`}>
        <Flag size={compact ? 13 : 12} />{!compact && " Report"}
      </button>
      {open && (
        <div onClick={() => setOpen(false)} data-testid="report-modal" className="fixed inset-0 z-[1300] bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-[#121214] border border-white/10 rounded-sm w-full max-w-md p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="font-unbounded font-semibold text-sm flex items-center gap-2"><Flag size={13} className="text-[#FF4D4D]" /> Report this {targetType}</div>
              <button type="button" onClick={() => setOpen(false)} className="text-zinc-500"><X size={15} /></button>
            </div>
            <select data-testid="report-reason" value={reason} onChange={(e) => setReason(e.target.value)} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 text-sm outline-none focus:border-[#FF4D4D]">
              {Object.entries(REPORT_REASONS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
            <textarea data-testid="report-details" rows={3} maxLength={1500} value={details} onChange={(e) => setDetails(e.target.value)} placeholder="Anything that helps us review (optional)"
              className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 text-sm outline-none focus:border-[#FF4D4D]" />
            <div className="text-[11px] text-zinc-500">Reports are anonymous to the person reported.</div>
            <button data-testid="report-submit" disabled={busy} className="w-full !py-2.5 text-xs font-semibold uppercase tracking-widest rounded-sm bg-[#FF4D4D] text-black hover:bg-[#ff6b6b] flex items-center justify-center gap-2">
              {busy ? <Loader2 size={12} className="animate-spin" /> : <Flag size={12} />} Send report
            </button>
          </form>
        </div>
      )}
    </>
  );
}
