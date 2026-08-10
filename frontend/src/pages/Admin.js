import React, { useEffect, useState } from "react";
import { api, fileUrl } from "../api";
import { toast } from "sonner";
import { Link } from "react-router-dom";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export default function AdminDashboard() {
  const [tab, setTab] = useState("overview");
  const [stats, setStats] = useState(null);
  const [settings, setSettings] = useState(null);
  const [submissions, setSubmissions] = useState([]);
  const [allArt, setAllArt] = useState([]);
  const [orders, setOrders] = useState([]);
  const [artists, setArtists] = useState([]);
  const [mentors, setMentors] = useState([]);

  const load = () => {
    api.get("/admin/stats").then((r) => setStats(r.data));
    api.get("/admin/settings").then((r) => setSettings(r.data));
    api.get("/admin/aotw/submissions").then((r) => setSubmissions(r.data));
    api.get("/artworks?limit=500").then((r) => setAllArt(r.data));
    api.get("/admin/orders").then((r) => setOrders(r.data));
    api.get("/admin/artists").then((r) => setArtists(r.data));
    api.get("/admin/mentorship").then((r) => setMentors(r.data));
  };
  useEffect(load, []);

  const saveSettings = async () => {
    await api.patch("/admin/settings", {
      commission_percent: Number(settings.commission_percent),
      upload_fee: Number(settings.upload_fee),
      currency: settings.currency,
    });
    toast.success("Settings saved");
  };
  const toggleFeatured = async (art) => {
    await api.post("/admin/featured", { artwork_id: art.id, featured: !art.featured });
    load();
  };
  const pickAotw = async (id) => {
    await api.post("/admin/aotw", { artwork_id: id });
    toast.success("Set as Featured Piece");
    load();
  };
  const flagArtist = async (aid) => {
    const note = prompt("Note for mentorship flag");
    if (!note) return;
    await api.post("/admin/mentorship", { artist_id: aid, note });
    toast.success("Flagged");
    load();
  };
  const resolveMentor = async (id) => {
    await api.patch(`/admin/mentorship/${id}/resolve`);
    load();
  };

  const tabs = [
    ["overview", "Overview"],
    ["settings", "Settings"],
    ["curation", "Curation"],
    ["aotw", "Featured"],
    ["orders", "Orders"],
    ["artists", "Artists"],
    ["mentorship", "Mentorship"],
  ];

  return (
    <div data-testid="admin-dashboard" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]">Admin</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4 mb-12">Command Desk</h1>

      <div className="flex flex-wrap gap-1 mb-12 border-b border-white/8">
        {tabs.map(([k, l]) => (
          <button key={k} data-testid={`tab-${k}`} onClick={() => setTab(k)}
            className={`label-caps text-xs px-4 py-3 border-b-2 transition-colors ${tab === k ? "border-[#CCFF00] text-white" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}>
            {l}
          </button>
        ))}
      </div>

      {tab === "overview" && stats && (
        <div className="grid md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard label="Revenue" value={`$${stats.revenue.toLocaleString()}`} accent="#CCFF00" />
          <StatCard label="Platform Take" value={`$${stats.platform_take.toLocaleString()}`} accent="#7C3AED" />
          <StatCard label="Orders" value={stats.total_orders} accent="#FFFFFF" />
          <StatCard label="Artists" value={stats.artists} accent="#FF4D4D" />
          <StatCard label="Buyers" value={stats.buyers} accent="#FFFFFF" />
          <StatCard label="Live pieces" value={stats.artworks_live} accent="#CCFF00" />
        </div>
      )}

      {tab === "settings" && settings && (
        <div className="max-w-lg glass-card p-8 space-y-5 rounded-sm">
          <Row label="Commission %">
            <input data-testid="commission-input" type="number" step="0.1" value={settings.commission_percent}
              onChange={(e) => setSettings({ ...settings, commission_percent: e.target.value })}
              className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none" />
          </Row>
          <Row label="Upload fee (USD)">
            <input data-testid="fee-input" type="number" step="0.5" value={settings.upload_fee}
              onChange={(e) => setSettings({ ...settings, upload_fee: e.target.value })}
              className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none" />
          </Row>
          <Row label="Currency">
            <input data-testid="currency-input" value={settings.currency}
              onChange={(e) => setSettings({ ...settings, currency: e.target.value })}
              className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none" />
          </Row>
          <button data-testid="save-settings" onClick={saveSettings} className="btn-lime">Save</button>
        </div>
      )}

      {tab === "curation" && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {allArt.map((a) => (
            <div key={a.id} className="border border-white/8 rounded-sm">
              <img src={resolveImg(a.images?.[0])} className="w-full aspect-square object-cover" alt="" />
              <div className="p-3">
                <div className="font-unbounded text-sm truncate">{a.title}</div>
                <div className="text-xs text-zinc-500">${a.price}</div>
                <button data-testid={`feature-${a.id}`} onClick={() => toggleFeatured(a)}
                  className={`mt-3 w-full py-2 label-caps text-xs rounded-sm ${a.featured ? "bg-[#CCFF00] text-black" : "border border-white/15 text-zinc-300 hover:border-[#CCFF00]"}`}>
                  {a.featured ? "Featured ★" : "Feature"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "aotw" && (
        submissions.length === 0 ? <div className="text-zinc-500 label-caps">No submissions yet.</div> : (
          <div className="grid md:grid-cols-3 gap-4">
            {submissions.map((a) => (
              <div key={a.id} className="border border-white/8 rounded-sm">
                <img src={resolveImg(a.images?.[0])} className="w-full aspect-square object-cover" alt="" />
                <div className="p-4">
                  <div className="font-unbounded text-lg">{a.title}</div>
                  <div className="text-xs text-zinc-500 mt-1">by {a.artist?.name}</div>
                  {a.aotw ? <div className="label-caps mt-3 text-[#CCFF00]">Currently Featured</div>
                    : <button data-testid={`pick-aotw-${a.id}`} onClick={() => pickAotw(a.id)} className="btn-lime mt-3 w-full">Feature This</button>}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {tab === "orders" && (
        orders.length === 0 ? <div className="text-zinc-500 label-caps">No orders yet.</div> : (
          <div className="border border-white/8 divide-y divide-white/8 text-sm rounded-sm">
            {orders.map((o) => (
              <div key={o.id} className="p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-zinc-400">{new Date(o.created_at).toLocaleString()}</div>
                <div>{o.items.length} piece(s)</div>
                <div className="font-anton text-xl">${o.total.toLocaleString()}</div>
                <div className="text-[#CCFF00] label-caps">Take: ${o.platform_take.toFixed(2)}</div>
              </div>
            ))}
          </div>
        )
      )}

      {tab === "artists" && (
        <div className="border border-white/8 divide-y divide-white/8 text-sm rounded-sm">
          {artists.map((a) => (
            <div key={a.id} className="p-4 flex items-center flex-wrap gap-4">
              <div className="flex-1 min-w-[200px]">
                <div className="font-unbounded text-lg font-semibold">{a.name}</div>
                <div className="text-zinc-500 text-xs">{a.email}</div>
              </div>
              <Link to={`/artist/${a.id}`} className="label-caps hover:text-[#CCFF00]">Portfolio</Link>
              <button data-testid={`flag-${a.id}`} onClick={() => flagArtist(a.id)} className="btn-ghost !py-2 !text-xs">Flag Mentorship</button>
            </div>
          ))}
        </div>
      )}

      {tab === "mentorship" && (
        mentors.length === 0 ? <div className="text-zinc-500 label-caps">Nothing flagged.</div> : (
          <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
            {mentors.map((m) => (
              <div key={m.id} className="p-4 flex flex-wrap items-center gap-4">
                <div className="flex-1 min-w-[200px]">
                  <div className="font-unbounded text-lg font-semibold">{m.artist?.name}</div>
                  <div className="text-sm text-zinc-400 mt-1">{m.note}</div>
                  <div className="text-xs text-zinc-500 mt-1">{m.artist?.email}</div>
                </div>
                {m.resolved ? <div className="label-caps text-[#CCFF00]">Resolved</div>
                  : <button data-testid={`resolve-${m.id}`} onClick={() => resolveMentor(m.id)} className="btn-ghost !py-2 !text-xs">Mark reached out</button>}
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}

function Row({ label, children }) {
  return <div><div className="label-caps mb-2">{label}</div>{children}</div>;
}
function StatCard({ label, value, accent }) {
  return (
    <div className="glass-card p-5 rounded-sm">
      <div className="label-caps">{label}</div>
      <div className="font-anton text-3xl mt-3" style={{ color: accent }}>{value}</div>
    </div>
  );
}
