import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { CheckCircle2, AlertTriangle, XCircle, Info, RefreshCw, ExternalLink, Rocket } from "lucide-react";

const STYLE = {
  pass: { icon: CheckCircle2, color: "#CCFF00", label: "Ready" },
  warn: { icon: AlertTriangle, color: "#F5A623", label: "Check" },
  fail: { icon: XCircle, color: "#FF4D4D", label: "Blocking" },
  info: { icon: Info, color: "#8b8b93", label: "Optional" },
};
const GROUPS = [["money", "Money"], ["domain", "Domain & email"], ["safety", "Safety"], ["content", "Content"]];

export function LaunchPanel() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async () => { setBusy(true); try { const r = await api.get("/admin/launch-readiness"); setData(r.data); } catch {} setBusy(false); };
  useEffect(() => { load(); }, []);
  if (!data) return <div className="py-16 text-center label-caps text-zinc-500" data-testid="launch-loading">Running checks…</div>;
  const total = data.checks.filter((c) => c.status !== "info").length;
  const done = data.counts.pass;
  return (
    <div data-testid="launch-panel" className="space-y-8">
      <div className="glass-card p-6 rounded-sm flex flex-wrap items-center gap-6">
        <div className="w-14 h-14 rounded-full flex items-center justify-center shrink-0" style={{ background: data.ready ? "#CCFF0020" : "#FF4D4D20", color: data.ready ? "#CCFF00" : "#FF4D4D" }}><Rocket size={24} /></div>
        <div className="flex-1 min-w-[220px]">
          <div className="font-anton text-3xl uppercase" data-testid="launch-headline">{data.ready ? "Cleared for launch" : `${data.counts.fail} blocker${data.counts.fail === 1 ? "" : "s"} left`}</div>
          <div className="text-sm text-zinc-400 mt-1" data-testid="launch-progress-text">{done} of {total} checks ready · {data.counts.warn} to review · checked {new Date(data.checked_at).toLocaleTimeString()}</div>
          <div className="h-1.5 bg-white/10 rounded-full mt-3 overflow-hidden"><div className="h-full bg-[#CCFF00] transition-[width] duration-700" style={{ width: `${Math.round((done / Math.max(total, 1)) * 100)}%` }} /></div>
        </div>
        <button data-testid="launch-rerun" onClick={load} disabled={busy} className="btn-ghost !py-2 !text-xs"><RefreshCw size={12} className={`mr-1 ${busy ? "animate-spin" : ""}`} /> Re-run checks</button>
      </div>
      {GROUPS.map(([g, label]) => {
        const rows = data.checks.filter((c) => c.group === g);
        if (!rows.length) return null;
        return (
          <div key={g}>
            <div className="label-caps mb-3">{label}</div>
            <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
              {rows.map((c) => <Row key={c.key} c={c} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Row({ c }) {
  const st = STYLE[c.status] || STYLE.info;
  const Icon = st.icon;
  return (
    <div data-testid={`launch-check-${c.key}`} data-status={c.status} className="p-4 flex gap-4">
      <Icon size={20} className="shrink-0 mt-0.5" style={{ color: st.color }} />
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <div className="font-unbounded font-semibold text-sm">{c.title}</div>
          <span className="label-caps text-[9px] px-1.5 py-0.5 border rounded-sm" style={{ color: st.color, borderColor: st.color }}>{st.label}</span>
        </div>
        <div className="text-sm text-zinc-300 mt-1 break-words">{c.detail}</div>
        {c.status !== "pass" && c.fix && <div className="text-xs text-zinc-500 mt-2 leading-relaxed"><span className="text-zinc-400">How to fix:</span> {c.fix}</div>}
        {(c.link || c.external) && (
          <div className="flex flex-wrap gap-3 mt-2">
            {c.link && <Link to={c.link} data-testid={`launch-link-${c.key}`} className="label-caps text-[#CCFF00] hover:text-white">Open →</Link>}
            {c.external && <a href={c.external} target="_blank" rel="noreferrer" data-testid={`launch-ext-${c.key}`} className="label-caps text-zinc-400 hover:text-white inline-flex items-center gap-1">Dashboard <ExternalLink size={10} /></a>}
          </div>
        )}
      </div>
    </div>
  );
}
