import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Flag, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, thumbUrl } from "../../api";
import { REPORT_REASONS } from "../ReportButton";

const linkFor = (r) => ({ artwork: `/artwork/${r.target_id}`, post: `/feed`, user: `/artist/${r.target_id}`, event: `/events/${r.target_id}` }[r.target_type]);
const ACTIONS = [["dismiss", "Dismiss", "btn-ghost"], ["warn_user", "Warn owner", "btn-ghost !text-[#F5A623] !border-[#F5A623]/40"], ["remove_content", "Remove content", "btn-ghost !text-[#FF4D4D] !border-[#FF4D4D]/40"], ["suspend_user", "Suspend owner", "!bg-[#FF4D4D] !text-black rounded-sm px-3"]];

export function ReportsPanel() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("open");
  const [busy, setBusy] = useState(null);
  const [notes, setNotes] = useState({});
  const load = () => api.get(`/admin/reports${filter === "all" ? "" : `?status=${filter}`}`).then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, [filter]); // eslint-disable-line

  const act = async (r, action) => {
    if (action !== "dismiss" && !confirm(`${action.replace("_", " ")} — are you sure?`)) return;
    setBusy(r.id);
    try { await api.post(`/admin/reports/${r.id}/resolve`, { action, note: notes[r.id] || null }); toast.success("Report resolved"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(null);
  };

  // group open reports on the same target
  const grouped = Object.values(items.reduce((acc, r) => { const k = `${r.target_type}:${r.target_id}:${r.status}`; (acc[k] = acc[k] || { ...r, count: 0, reasons: new Set() }); acc[k].count += 1; acc[k].reasons.add(r.reason); return acc; }, {}));

  return (
    <div data-testid="reports-panel">
      <div className="flex gap-2 mb-6">
        {[["open", "Open"], ["resolved", "Resolved"], ["all", "All"]].map(([k, l]) => (
          <button key={k} data-testid={`reports-filter-${k}`} onClick={() => setFilter(k)} className={`label-caps text-xs px-3 py-2 border rounded-sm ${filter === k ? "border-[#CCFF00] text-[#CCFF00]" : "border-white/10 text-zinc-500"}`}>{l}</button>
        ))}
      </div>
      {grouped.length === 0 ? <div className="border border-dashed border-white/10 p-12 text-center label-caps text-zinc-500">No {filter === "all" ? "" : filter} reports.</div> : (
        <div className="space-y-4">
          {grouped.map((r) => (
            <div key={r.id} data-testid={`report-${r.id}`} className="border border-white/8 rounded-sm p-5">
              <div className="flex flex-wrap items-start gap-4">
                {r.target?.image && <img src={thumbUrl(r.target.image, 240)} alt="" className="w-16 h-16 object-cover rounded-sm" />}
                <div className="flex-1 min-w-[220px]">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="label-caps text-[10px] px-2 py-0.5 rounded-sm bg-[#FF4D4D]/20 text-[#FF4D4D]">{r.target_type}</span>
                    <Link to={linkFor(r)} className="font-unbounded font-semibold text-sm hover:text-[#CCFF00]">{r.target?.title || r.target_id.slice(0, 8)}</Link>
                    {r.count > 1 && <span className="label-caps text-[10px] px-2 py-0.5 rounded-sm bg-white/10 text-zinc-300 flex items-center gap-1"><Flag size={9} /> {r.count} reports</span>}
                    {r.target?.removed && <span className="label-caps text-[10px] text-zinc-500">removed</span>}
                    {r.owner?.suspended && <span className="label-caps text-[10px] text-[#FF4D4D]">owner suspended</span>}
                  </div>
                  <div className="text-xs text-zinc-500 mt-1">Owner: {r.owner?.name || "—"} · Reported by {r.reporter?.name} · {new Date(r.created_at).toLocaleString()}</div>
                  <div className="text-sm text-zinc-300 mt-2"><span className="text-[#F5A623] label-caps text-[10px] mr-2">{[...r.reasons].map((x) => REPORT_REASONS[x] || x).join(", ")}</span>{r.details}</div>
                  {r.status !== "open" && <div className="text-xs text-zinc-500 mt-2">Resolved: {r.action}{r.note ? ` · "${r.note}"` : ""}</div>}
                </div>
              </div>
              {r.status === "open" && (
                <div className="mt-4 pt-4 border-t border-white/8 flex flex-wrap items-center gap-2">
                  <input data-testid={`report-note-${r.id}`} placeholder="Note to owner (optional)" value={notes[r.id] || ""} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
                    className="flex-1 min-w-[180px] bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 text-xs outline-none focus:border-[#CCFF00]" />
                  {ACTIONS.map(([a, l, cls]) => (
                    <button key={a} data-testid={`report-${a}-${r.id}`} disabled={busy === r.id} onClick={() => act(r, a)} className={`${cls} !py-2 !text-xs flex items-center gap-1`}>
                      {busy === r.id ? <Loader2 size={11} className="animate-spin" /> : null} {l}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
