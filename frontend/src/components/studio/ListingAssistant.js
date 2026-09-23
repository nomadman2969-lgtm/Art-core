import React, { useState } from "react";
import { api } from "../../api";
import { toast } from "sonner";
import { Sparkles, Loader2, Check } from "lucide-react";

export function ListingAssistant({ imagePath, form, onApply }) {
  const [hints, setHints] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState(null);

  if (!imagePath) return null;

  const run = async () => {
    setBusy(true);
    try {
      const r = await api.post("/studio/listing-assist", {
        image_path: imagePath, section: form.section, hints: hints || null,
        width_in: Number(form.width_in) || null, height_in: Number(form.height_in) || null, kind: form.kind,
      });
      setDraft(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Assistant unavailable — try again"); }
    setBusy(false);
  };

  const apply = () => {
    onApply({
      title: draft.title, description: draft.description, medium: draft.medium, style: draft.style, color: draft.color,
      tags: (draft.tags || []).join(", "), price: draft.price_suggested,
      ...(form.section === "upcycle" && draft.furniture_type ? { furniture_type: draft.furniture_type, materials: draft.materials || form.materials } : {}),
    });
    toast.success("Draft applied — edit anything before publishing");
  };

  return (
    <div data-testid="listing-assistant" className="glass-card rounded-sm p-5 border border-[#7C3AED]/40">
      <div className="label-caps text-[#7C3AED] flex items-center gap-2"><Sparkles size={12} /> Listing assistant · Claude</div>
      <div className="text-sm text-zinc-300 mt-2">Let AI draft the title, description, tags and a price range from your photo. You stay in control — everything is editable.</div>
      <div className="flex flex-col sm:flex-row gap-2 mt-3">
        <input data-testid="assist-hints" value={hints} onChange={(e) => setHints(e.target.value)} maxLength={600}
          placeholder="Optional: what is it, what inspired it, materials, how long it took…"
          className="flex-1 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 text-sm outline-none focus:border-[#7C3AED]" />
        <button type="button" data-testid="assist-run-btn" onClick={run} disabled={busy} className="btn-violet !py-2 !text-xs inline-flex items-center gap-2 justify-center">
          {busy ? <><Loader2 size={12} className="animate-spin" /> Looking at your piece…</> : <><Sparkles size={12} /> {draft ? "Draft again" : "Draft my listing"}</>}
        </button>
      </div>
      {draft && (
        <div data-testid="assist-draft" className="mt-4 border-t border-white/8 pt-4 space-y-2 text-sm">
          <div className="font-unbounded font-semibold text-base" data-testid="assist-title">{draft.title}</div>
          <p className="text-zinc-300 leading-relaxed">{draft.description}</p>
          <div className="flex flex-wrap gap-1.5">{(draft.tags || []).map((t) => <span key={t} className="label-caps text-[10px] px-2 py-1 border border-white/10 rounded-sm">{t}</span>)}</div>
          <div className="text-xs text-zinc-400">{draft.medium}{draft.style ? ` · ${draft.style}` : ""}{draft.color ? ` · ${draft.color}` : ""}</div>
          <div className="flex items-baseline gap-3 mt-2">
            <span className="label-caps text-zinc-500">Suggested price</span>
            <span className="font-anton text-2xl text-[#CCFF00]" data-testid="assist-price">${draft.price_suggested}</span>
            <span className="text-xs text-zinc-500">range ${draft.price_low}–${draft.price_high}</span>
          </div>
          {draft.price_note && <div className="text-xs text-zinc-500">{draft.price_note}</div>}
          <button type="button" data-testid="assist-apply-btn" onClick={apply} className="btn-lime !py-2 !text-xs inline-flex items-center gap-2 mt-2"><Check size={12} /> Use this draft</button>
        </div>
      )}
    </div>
  );
}
