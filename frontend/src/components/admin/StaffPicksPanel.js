import React, { useEffect, useState } from "react";
import { Loader2, Star } from "lucide-react";
import { toast } from "sonner";
import { api, thumbUrl } from "../../api";

export function StaffPicksPanel() {
  const [arts, setArts] = useState([]);
  const [events, setEvents] = useState([]);
  const [form, setForm] = useState({ title: "Staff Picks", blurb: "", artwork_ids: [], event_ids: [] });
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/artworks?limit=120").then((r) => setArts(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => {});
    api.get("/events").then((r) => setEvents(r.data)).catch(() => {});
    api.get("/staff-picks").then((r) => setForm({ title: r.data.title || "Staff Picks", blurb: r.data.blurb || "", artwork_ids: r.data.artworks.map((a) => a.id), event_ids: r.data.events.map((e) => e.id) })).catch(() => {});
  }, []);

  const toggle = (key, id, max) => setForm((f) => {
    const has = f[key].includes(id);
    if (!has && f[key].length >= max) { toast.error(`Max ${max}`); return f; }
    return { ...f, [key]: has ? f[key].filter((x) => x !== id) : [...f[key], id] };
  });
  const save = async () => {
    setBusy(true);
    try { await api.put("/admin/staff-picks", form); toast.success("Staff Picks published to the home page"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };
  const shown = arts.filter((a) => !q || a.title.toLowerCase().includes(q.toLowerCase()) || (a.artist?.name || "").toLowerCase().includes(q.toLowerCase()));
  const inputCls = "bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 text-sm outline-none focus:border-[#D4AF37]";

  return (
    <div data-testid="staff-picks-panel" className="space-y-6">
      <div className="grid md:grid-cols-[1fr_2fr_auto] gap-3">
        <input data-testid="picks-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Collection title" className={inputCls} />
        <input data-testid="picks-blurb" value={form.blurb} onChange={(e) => setForm({ ...form, blurb: e.target.value })} placeholder="One-line blurb (optional)" className={inputCls} />
        <button data-testid="picks-save" onClick={save} disabled={busy} className="btn-lime !py-2 !px-4 text-xs flex items-center gap-2">{busy ? <Loader2 size={12} className="animate-spin" /> : <Star size={12} />} Publish</button>
      </div>
      <div>
        <div className="flex items-center justify-between mb-2"><div className="label-caps text-zinc-400">Artworks · {form.artwork_ids.length}/12</div>
          <input data-testid="picks-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title / artist" className={`${inputCls} !py-1.5 text-xs`} /></div>
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2 max-h-[420px] overflow-y-auto pr-1">
          {shown.map((a) => { const on = form.artwork_ids.includes(a.id); return (
            <button key={a.id} data-testid={`pick-art-${a.id}`} onClick={() => toggle("artwork_ids", a.id, 12)} className={`relative rounded-sm overflow-hidden border text-left ${on ? "border-[#D4AF37]" : "border-white/8 hover:border-white/30"}`}>
              <div className="aspect-square bg-white/[0.03]">{a.images?.[0] && <img src={thumbUrl(a.images[0], 240)} alt="" loading="lazy" className="w-full h-full object-cover" />}</div>
              <div className="p-1.5 text-[10px] truncate">{a.title}</div>
              {on && <div className="absolute top-1 right-1 w-5 h-5 rounded-full bg-[#D4AF37] text-black text-[10px] flex items-center justify-center font-bold">{form.artwork_ids.indexOf(a.id) + 1}</div>}
            </button>); })}
        </div>
      </div>
      <div>
        <div className="label-caps text-zinc-400 mb-2">Events · {form.event_ids.length}/6</div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {events.map((e) => { const on = form.event_ids.includes(e.id); return (
            <button key={e.id} data-testid={`pick-event-${e.id}`} onClick={() => toggle("event_ids", e.id, 6)} className={`flex items-center gap-3 p-2 rounded-sm border text-left ${on ? "border-[#D4AF37]" : "border-white/8 hover:border-white/30"}`}>
              <div className="w-12 h-12 rounded-sm bg-white/[0.03] flex-shrink-0 overflow-hidden">{e.cover_image && <img src={thumbUrl(e.cover_image, 240)} alt="" className="w-full h-full object-cover" />}</div>
              <div className="min-w-0"><div className="text-xs font-semibold truncate">{e.title}</div><div className="text-[10px] text-zinc-500">{new Date(e.start_at).toLocaleDateString()} · {e.host_name}</div></div>
            </button>); })}
        </div>
      </div>
    </div>
  );
}
