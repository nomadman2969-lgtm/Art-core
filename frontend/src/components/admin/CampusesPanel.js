import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { toast } from "sonner";
import { Check, X, Star, Merge, Search } from "lucide-react";

export function CampusesPanel() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("pending");
  const [q, setQ] = useState("");
  const [mergeId, setMergeId] = useState(null);
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/admin/campuses", { params: { status: filter === "all" ? undefined : filter, q } }).then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { const t = setTimeout(load, 200); return () => clearTimeout(t); }, [filter, q]);

  const patch = async (c, body, msg) => {
    setBusy(true);
    try { await api.patch(`/admin/campuses/${c.id}`, body); toast.success(msg); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };
  const merge = async (c) => {
    if (!target) return;
    setBusy(true);
    try {
      const r = await api.post(`/admin/campuses/${c.id}/merge`, { into_id: target });
      toast.success(`Merged into ${r.data.into.name} — ${r.data.moved_artists} artist(s) moved`);
      setMergeId(null); setTarget(""); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Merge failed"); }
    setBusy(false);
  };
  const pending = items.filter((c) => c.status === "pending").length;

  return (
    <div data-testid="campuses-panel" className="space-y-4">
      <div className="text-sm text-zinc-400 max-w-2xl">Schools artists tag themselves with. Seeded list is approved already; artist-added schools land here as <span className="text-[#F5A623]">pending</span>. Approve, rename, feature on the campus directory, or merge duplicates (artists move over automatically).</div>
      <div className="flex flex-wrap gap-2 items-center">
        {["pending", "approved", "rejected", "all"].map((f) => (
          <button key={f} data-testid={`campus-filter-${f}`} onClick={() => setFilter(f)} className={`label-caps text-xs px-3 py-2 border rounded-sm ${filter === f ? "border-[#CCFF00] text-white" : "border-white/10 text-zinc-500 hover:text-zinc-300"}`}>
            {f}{f === "pending" && pending > 0 && filter === "pending" ? ` (${pending})` : ""}
          </button>
        ))}
        <div className="flex items-center gap-2 bg-white/[0.03] border border-white/12 rounded-sm px-3 ml-auto">
          <Search size={14} className="text-zinc-500" />
          <input data-testid="campus-admin-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search schools" className="bg-transparent py-2 outline-none text-sm" />
        </div>
      </div>
      {items.length === 0 ? <div className="text-zinc-500 label-caps py-16 text-center">Nothing here.</div> : (
        <div className="border border-white/8 divide-y divide-white/8 rounded-sm text-sm">
          {items.map((c) => (
            <div key={c.id} data-testid={`campus-row-${c.id}`} className="p-4">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex-1 min-w-[240px]">
                  <div className="font-unbounded font-semibold flex items-center gap-2 flex-wrap">
                    <Link to={`/campus/${c.slug}`} className="hover:text-[#CCFF00]">{c.name}</Link>
                    <span className="label-caps text-[9px] px-1.5 py-0.5 rounded-sm border" style={{ color: c.status === "pending" ? "#F5A623" : c.status === "rejected" ? "#FF4D4D" : "#CCFF00", borderColor: "currentColor" }}>{c.status}</span>
                    {c.featured && <Star size={12} className="text-[#CCFF00]" />}
                  </div>
                  <div className="text-xs text-zinc-500 mt-1">{[c.city, c.country].filter(Boolean).join(" · ") || "—"} · {c.artist_count} artist(s){c.created_by ? ` · added by ${c.created_by.name} (${c.created_by.email})` : c.seeded ? " · seeded" : ""}</div>
                </div>
                {c.status !== "approved" && <button data-testid={`campus-approve-${c.id}`} disabled={busy} onClick={() => patch(c, { status: "approved" }, "Approved")} className="btn-lime !py-2 !text-xs"><Check size={12} className="mr-1" /> Approve</button>}
                {c.status !== "rejected" && <button data-testid={`campus-reject-${c.id}`} disabled={busy} onClick={() => patch(c, { status: "rejected" }, "Rejected — artists untagged")} className="btn-ghost !py-2 !text-xs !border-[#FF4D4D]/50 !text-[#FF4D4D]"><X size={12} className="mr-1" /> Reject</button>}
                <button data-testid={`campus-feature-${c.id}`} disabled={busy} onClick={() => patch(c, { featured: !c.featured }, c.featured ? "Unfeatured" : "Featured on directory")} className="btn-ghost !py-2 !text-xs"><Star size={12} className="mr-1" /> {c.featured ? "Unfeature" : "Feature"}</button>
                <button data-testid={`campus-rename-${c.id}`} disabled={busy} onClick={() => { const n = window.prompt("New name", c.name); if (n && n.trim().length >= 3) patch(c, { name: n.trim() }, "Renamed"); }} className="btn-ghost !py-2 !text-xs">Rename</button>
                <button data-testid={`campus-merge-toggle-${c.id}`} onClick={() => { setMergeId(mergeId === c.id ? null : c.id); setTarget(""); }} className="btn-ghost !py-2 !text-xs"><Merge size={12} className="mr-1" /> Merge</button>
              </div>
              {mergeId === c.id && <MergeInto c={c} target={target} setTarget={setTarget} onMerge={() => merge(c)} busy={busy} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MergeInto({ c, target, setTarget, onMerge, busy }) {
  const [q, setQ] = useState("");
  const [opts, setOpts] = useState([]);
  useEffect(() => {
    if (q.trim().length < 2) { setOpts([]); return; }
    const t = setTimeout(() => api.get("/campus/search", { params: { q } }).then((r) => setOpts(r.data.filter((o) => o.id !== c.id))).catch(() => {}), 200);
    return () => clearTimeout(t);
  }, [q, c.id]);
  const chosen = opts.find((o) => o.id === target);
  return (
    <div className="mt-3 p-3 bg-white/[0.02] border border-white/8 rounded-sm flex flex-wrap items-center gap-3" data-testid={`campus-merge-${c.id}`}>
      <div className="label-caps text-zinc-400">Merge “{c.name}” into</div>
      <input data-testid={`campus-merge-search-${c.id}`} value={q} onChange={(e) => { setQ(e.target.value); setTarget(""); }} placeholder="Search target school" className="bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none text-sm min-w-[240px]" />
      {opts.length > 0 && !chosen && (
        <select data-testid={`campus-merge-select-${c.id}`} value={target} onChange={(e) => setTarget(e.target.value)} className="bg-[#121214] border border-white/12 rounded-sm px-3 py-2 text-sm">
          <option value="">Pick…</option>
          {opts.map((o) => <option key={o.id} value={o.id}>{o.name}{o.city ? ` — ${o.city}` : ""}</option>)}
        </select>
      )}
      {chosen && <span className="text-sm text-[#CCFF00]">{chosen.name}</span>}
      <button data-testid={`campus-merge-confirm-${c.id}`} disabled={!target || busy} onClick={onMerge} className="btn-coral !py-2 !text-xs disabled:opacity-40">Merge now</button>
    </div>
  );
}
