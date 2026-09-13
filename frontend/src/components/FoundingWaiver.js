import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles, Clock } from "lucide-react";
import { toast } from "sonner";
import { api } from "../api";

export function useWaiverSettings() {
  const [w, setW] = useState(null);
  useEffect(() => { api.get("/settings").then((r) => setW(r.data)).catch(() => {}); }, []);
  return w;
}

export function FoundingBanner({ compact = false }) {
  const w = useWaiverSettings();
  if (!w || !w.waiver_enabled) return null;
  return (
    <div className={`relative overflow-hidden rounded-sm border border-[#CCFF00]/40 bg-[#CCFF00]/[0.06] ${compact ? "p-4" : "p-5 md:p-6"}`} data-testid="founding-banner">
      <div className="absolute -right-10 -top-10 w-40 h-40 bg-[#CCFF00] opacity-10 blur-3xl rounded-full" />
      <div className="relative flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1">
          <div className="label-caps text-[#CCFF00] flex items-center gap-2"><Sparkles size={12} /> Founding artist offer</div>
          <div className={`font-anton uppercase mt-2 leading-[0.95] ${compact ? "text-2xl" : "text-3xl md:text-4xl"}`} data-testid="founding-headline">
            <span className="text-[#CCFF00]">0% fees</span> for your first {w.waiver_days} days
          </div>
          <div className="text-xs md:text-sm text-zinc-400 mt-2 max-w-xl">
            Open a studio and Art Core takes nothing on your first {w.waiver_max_sales} sales in your first {w.waiver_days} days — you keep everything except standard card processing.
            {w.founding_enabled && w.founding_left > 0 && (
              <> Then, as a founding artist, your rate is <span className="text-white">locked at {w.founding_rate}% for life</span> — even when the standard rate changes.</>
            )}
          </div>
          {w.founding_enabled && w.founding_left > 0 && (
            <div className="mt-3 flex items-center gap-3" data-testid="founding-spots">
              <div className="h-1.5 flex-1 max-w-xs bg-white/[0.06] rounded-sm overflow-hidden"><div className="h-full bg-[#CCFF00]" style={{ width: `${Math.min(100, (w.founding_taken / Math.max(1, w.founding_cap)) * 100)}%` }} /></div>
              <div className="label-caps text-[10px] text-[#CCFF00]">{w.founding_left} of {w.founding_cap} founding spots left</div>
            </div>
          )}
        </div>
        {!compact && <Link to="/register?role=artist" data-testid="founding-cta" className="btn-lime whitespace-nowrap">Claim 0% for {w.waiver_days} days</Link>}
      </div>
    </div>
  );
}

export function FoundingChip({ st }) {
  if (!st?.founding_member) return null;
  return (
    <div className="border border-white/10 rounded-sm p-4 flex items-center gap-3" data-testid="founding-chip">
      <div className="p-2 rounded-sm bg-white/[0.06] text-[#CCFF00] w-fit"><Sparkles size={16} /></div>
      <div className="min-w-0">
        <div className="font-unbounded text-sm">Founding artist <span className="text-zinc-500">#{st.founding_number}</span></div>
        <div className="text-xs text-zinc-400 mt-0.5" data-testid="founding-rate">
          Your Art Core fee is locked at <span className="text-[#CCFF00]">{st.locked_commission_percent}%</span> for life
          {st.standard_commission_percent > st.locked_commission_percent && <> · standard rate is now {st.standard_commission_percent}%</>}
        </div>
      </div>
    </div>
  );
}

export function WaiverBadge() {
  const [st, setSt] = useState(null);
  useEffect(() => { api.get("/waiver/me").then((r) => setSt(r.data)).catch(() => {}); }, []);
  if (!st) return null;
  if (!st.active) return <FoundingChip st={st} />;
  return (
    <div className="space-y-3">
    <FoundingChip st={st} />
    <div className="border border-[#CCFF00]/40 bg-[#CCFF00]/[0.06] rounded-sm p-4 flex flex-col sm:flex-row sm:items-center gap-3" data-testid="waiver-badge">
      <div className="p-2 rounded-sm bg-[#CCFF00]/15 text-[#CCFF00] w-fit"><Clock size={16} /></div>
      <div className="flex-1 min-w-0">
        <div className="font-unbounded text-sm"><span className="text-[#CCFF00]">Founding window · 0% Art Core fees</span></div>
        <div className="text-xs text-zinc-400 mt-0.5" data-testid="waiver-countdown">
          {st.days_left} day{st.days_left === 1 ? "" : "s"} left{st.sales_left != null ? ` · ${st.sales_left} fee-free sale${st.sales_left === 1 ? "" : "s"} remaining` : ""} · ends {new Date(st.until).toLocaleDateString()}
        </div>
      </div>
      <div className="text-[10px] text-zinc-500 sm:text-right">Card processing (~2.9% + 30¢) still applies</div>
    </div>
    </div>
  );
}

export function AdminWaiverButton({ userId, onDone }) {
  const [busy, setBusy] = useState(false);
  const extend = async () => {
    setBusy(true);
    try { const r = await api.post(`/admin/waiver/${userId}`, { days: 30 }); toast.success(`0% window now ends ${new Date(r.data.until).toLocaleDateString()}`); onDone?.(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Couldn't extend"); }
    finally { setBusy(false); }
  };
  const founding = async () => {
    setBusy(true);
    try { const r = await api.post(`/admin/waiver/founding/${userId}`); toast.success(`Founding artist #${r.data.founding_number} · ${r.data.locked_commission_percent}% locked`); onDone?.(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Couldn't grant"); }
    finally { setBusy(false); }
  };
  return <span className="inline-flex gap-2"><button data-testid={`founding-grant-${userId}`} onClick={founding} disabled={busy} className="label-caps text-[10px] text-zinc-300 hover:text-white border border-white/15 px-2 py-1 rounded-sm">Lock founding rate</button><button data-testid={`waiver-extend-${userId}`} onClick={extend} disabled={busy} className="label-caps text-[10px] text-[#CCFF00] hover:text-white border border-[#CCFF00]/30 px-2 py-1 rounded-sm">{busy ? "..." : "+30d 0% fees"}</button></span>;
}
