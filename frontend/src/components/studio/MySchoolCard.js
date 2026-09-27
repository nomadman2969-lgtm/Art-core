import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { toast } from "sonner";
import { SchoolPicker } from "../SchoolPicker";
import { ArrowRight } from "lucide-react";

// Artist's school — saves immediately to the user (not the studio draft).
export function MySchoolCard({ user, refresh }) {
  const [busy, setBusy] = useState(false);
  const [pendingNew, setPendingNew] = useState(null);
  const [city, setCity] = useState("");
  const campus = user?.campus || null;

  const persist = async (payload) => {
    setBusy(true);
    try {
      const r = await api.post("/campus/me", payload);
      await refresh?.();
      toast.success(r.data.status === "pending" ? "School added — we'll approve it shortly. You're already on its page." : "School saved");
      setPendingNew(null); setCity("");
    } catch (e) { toast.error(e?.response?.data?.detail || "Couldn't save school"); }
    setBusy(false);
  };
  const onChange = async (c) => {
    if (!c) {
      setBusy(true);
      try { await api.delete("/campus/me"); await refresh?.(); toast.success("School removed"); } catch { toast.error("Failed"); }
      setBusy(false);
      return;
    }
    if (c.isNew) { setPendingNew(c.name); return; }
    await persist({ campus_id: c.id });
  };

  return (
    <div className="glass-card rounded-sm p-5" data-testid="my-school-card">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="label-caps">Your school</div>
          <div className="text-sm text-zinc-400 mt-1">Tag your art school to appear on its campus page with classmates, their work and events.</div>
        </div>
        {campus?.slug && <Link to={`/campus/${campus.slug}`} data-testid="my-school-view" className="label-caps text-[#CCFF00] hover:text-white flex items-center gap-1">View campus <ArrowRight size={12} /></Link>}
      </div>
      <div className="mt-4">
        {pendingNew ? (
          <div data-testid="school-new-form" className="space-y-3">
            <div className="text-sm">Adding <span className="text-[#CCFF00]">{pendingNew}</span></div>
            <input data-testid="school-new-city" value={city} onChange={(e) => setCity(e.target.value)} placeholder="City (optional)"
              className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 outline-none focus:border-[#CCFF00] text-sm" />
            <div className="flex gap-2">
              <button type="button" data-testid="school-new-save" disabled={busy} onClick={() => persist({ name: pendingNew, city })} className="btn-lime !py-2 !text-xs">{busy ? "Saving…" : "Add school"}</button>
              <button type="button" data-testid="school-new-cancel" onClick={() => setPendingNew(null)} className="btn-ghost !py-2 !text-xs">Cancel</button>
            </div>
          </div>
        ) : (
          <SchoolPicker value={campus} onChange={onChange} disabled={busy} testid="my-school" />
        )}
      </div>
    </div>
  );
}
