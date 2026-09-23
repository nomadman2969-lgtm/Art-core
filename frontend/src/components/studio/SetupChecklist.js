import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, copyText, ORIGIN } from "../../api";
import { toast } from "sonner";
import { Check, X, Rocket, Share2 } from "lucide-react";

export function SetupChecklist({ userId, onTab }) {
  const [data, setData] = useState(null);

  const load = useCallback(() => api.get("/studio/setup-checklist").then((r) => setData(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const h = () => load();
    window.addEventListener("focus", h);
    return () => window.removeEventListener("focus", h);
  }, [load]);

  if (!data || data.dismissed || (data.complete && data.dismissed)) return null;

  const share = async () => {
    const url = `${ORIGIN}/artist/${userId}`;
    if (navigator.share) { try { await navigator.share({ title: "My Art Core studio", url }); } catch {} }
    else { copyText(url); toast.success("Studio link copied"); }
    await api.post("/studio/setup-checklist/shared").catch(() => {});
    load();
  };
  const dismiss = async () => { await api.post("/studio/setup-checklist/dismiss").catch(() => {}); setData((d) => ({ ...d, dismissed: true })); };
  const pct = Math.round((data.done / data.total) * 100);

  const go = (s) => {
    if (s.key === "share") return share();
    const m = s.href.match(/tab=(\w+)/);
    if (m && onTab) { onTab(m[1]); window.scrollTo({ top: 0, behavior: "smooth" }); }
  };

  return (
    <div data-testid="setup-checklist" className="glass-card rounded-sm p-6 mb-10 border border-[#CCFF00]/30 relative overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-1 bg-white/5"><div className="h-full bg-[#CCFF00] transition-[width] duration-500" style={{ width: `${pct}%` }} /></div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="label-caps text-[#CCFF00] flex items-center gap-2"><Rocket size={12} /> {data.complete ? "You're all set" : "Get set up"}</div>
          <div className="font-anton text-2xl md:text-3xl uppercase mt-2">{data.complete ? "Your studio is live and ready to sell" : `${data.done} of ${data.total} done`}</div>
          <div className="text-sm text-zinc-400 mt-1">{data.complete ? "Keep uploading — studios with 5+ pieces get 3× more visits." : "Artists who finish this list make their first sale 4× faster."}</div>
        </div>
        <button data-testid="checklist-dismiss" onClick={dismiss} className="text-zinc-500 hover:text-white shrink-0" aria-label="Dismiss"><X size={16} /></button>
      </div>
      <ol className="mt-5 grid sm:grid-cols-2 lg:grid-cols-5 gap-2">
        {data.steps.map((s, i) => {
          const inner = (
            <>
              <span className={`mt-0.5 shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${s.done ? "bg-[#CCFF00] text-black" : "border border-white/20 text-zinc-500"}`}>
                {s.done ? <Check size={12} /> : <span className="text-[10px] font-semibold">{i + 1}</span>}
              </span>
              <span className={`text-sm leading-snug ${s.done ? "text-zinc-500 line-through" : "text-zinc-200"}`}>{s.label}</span>
              {s.key === "share" && !s.done && <Share2 size={12} className="ml-auto text-zinc-500 shrink-0" />}
            </>
          );
          const cls = `flex items-start gap-3 p-3 rounded-sm border text-left w-full transition-colors ${s.done ? "border-white/5 bg-white/[0.02]" : "border-white/10 hover:border-[#CCFF00]/60 hover:bg-[#CCFF00]/5"}`;
          const usesTab = /tab=/.test(s.href) || s.key === "share";
          return (
            <li key={s.key}>
              {usesTab ? <button data-testid={`checklist-${s.key}`} onClick={() => go(s)} className={cls}>{inner}</button>
                : <Link data-testid={`checklist-${s.key}`} to={s.href} className={cls}>{inner}</Link>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

