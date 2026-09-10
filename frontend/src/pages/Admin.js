import React, { useEffect, useState } from "react";
import { api, fileUrl } from "../api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { DisputesPanel } from "../components/admin/DisputesPanel";
import { ReportsPanel } from "../components/admin/ReportsPanel";

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
  const [refundables, setRefundables] = useState([]);

  const load = () => {
    api.get("/admin/stats").then((r) => setStats(r.data));
    api.get("/admin/settings").then((r) => setSettings(r.data));
    api.get("/admin/aotw/submissions").then((r) => setSubmissions(r.data));
    api.get("/artworks?limit=500").then((r) => setAllArt(r.data));
    api.get("/admin/orders").then((r) => setOrders(r.data));
    api.get("/admin/artists").then((r) => setArtists(r.data));
    api.get("/admin/mentorship").then((r) => setMentors(r.data));
    api.get("/admin/refundable").then((r) => setRefundables(r.data)).catch(() => {});
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
    ["refunds", "Refunds"],
    ["disputes", "Disputes"],
    ["reports", "Reports"],
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

      {tab === "refunds" && (
        <RefundsPanel items={refundables} onReload={load} />
      )}
      {tab === "disputes" && <DisputesPanel />}
      {tab === "reports" && <ReportsPanel />}
    </div>
  );
}

function RefundsPanel({ items, onReload }) {
  const [openId, setOpenId] = useState(null);
  const [amt, setAmt] = useState("");
  const [reason, setReason] = useState("requested_by_customer");
  const [busy, setBusy] = useState(false);

  const doRefund = async (item, full) => {
    setBusy(true);
    try {
      const path = item.kind === "order" ? `/admin/orders/${item.id}/refund` : `/admin/commissions/${item.id}/refund`;
      const payload = { reason, reverse_payouts: true };
      if (!full) {
        const v = Number(amt);
        if (!v || v <= 0 || v > item.amount) { toast.error("Enter a valid partial amount"); setBusy(false); return; }
        payload.amount = v;
      }
      const r = await api.post(path, payload);
      toast.success(`Refunded $${r.data.refunded.toFixed(2)}${r.data.full ? " (full)" : ""}`);
      setOpenId(null); setAmt("");
      onReload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Refund failed"); }
    setBusy(false);
  };

  if (items.length === 0) {
    return <div className="text-zinc-500 label-caps py-16 text-center">No refundable transactions right now.</div>;
  }
  return (
    <div data-testid="refunds-panel" className="space-y-3">
      <div className="text-sm text-zinc-400 mb-4 max-w-2xl">
        One-click refund via Stripe. Platform commission is auto-refunded AND artist transfers are auto-reversed (Stripe Connect). Manually released payouts get flagged <span className="text-[#F5A623]">clawback_needed</span>.
      </div>
      {items.map((it) => {
        const isOpen = openId === it.id;
        return (
          <div key={it.id} data-testid={`refundable-${it.id}`} className="border border-white/8 rounded-sm">
            <div className="p-4 flex flex-wrap items-center gap-4">
              <div className="label-caps text-xs px-2 py-1 rounded-sm" style={{ background: it.kind === "commission" ? "#7C3AED30" : "#CCFF0030", color: it.kind === "commission" ? "#7C3AED" : "#CCFF00" }}>
                {it.kind === "commission" ? "Commission" : it.source || "Order"}
              </div>
              <div className="flex-1 min-w-[200px]">
                <div className="font-unbounded text-sm font-semibold">{it.kind === "commission" ? it.subject : `Order #${it.id.slice(0, 8)}`}</div>
                <div className="label-caps text-zinc-500 mt-1">{new Date(it.created_at).toLocaleString()}</div>
              </div>
              <div className="font-anton text-2xl text-[#CCFF00]">${Number(it.amount).toLocaleString()}</div>
              <button data-testid={`refund-toggle-${it.id}`} onClick={() => setOpenId(isOpen ? null : it.id)}
                className={`btn-ghost !py-2 !text-xs ${isOpen ? "!border-[#FF4D4D] !text-[#FF4D4D]" : ""}`}>
                {isOpen ? "Cancel" : "Refund"}
              </button>
            </div>
            {isOpen && (
              <div className="p-4 border-t border-white/8 bg-white/[0.02] space-y-3">
                <div className="grid md:grid-cols-2 gap-3">
                  <label className="block">
                    <div className="label-caps mb-2">Reason</div>
                    <select data-testid={`reason-${it.id}`} value={reason} onChange={(e) => setReason(e.target.value)}
                      className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#FF4D4D]">
                      <option value="requested_by_customer">Requested by customer</option>
                      <option value="duplicate">Duplicate charge</option>
                      <option value="fraudulent">Fraudulent</option>
                    </select>
                  </label>
                  <label className="block">
                    <div className="label-caps mb-2">Partial amount (leave empty = full)</div>
                    <input data-testid={`amount-${it.id}`} type="number" step="0.01" min="0" max={it.amount}
                      value={amt} onChange={(e) => setAmt(e.target.value)} placeholder={`$${Number(it.amount).toLocaleString()}`}
                      className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#FF4D4D]" />
                  </label>
                </div>
                <div className="flex gap-2">
                  <button data-testid={`refund-full-${it.id}`} disabled={busy} onClick={() => doRefund(it, true)} className="btn-coral !py-2 !text-xs">
                    {busy ? "Refunding..." : `Refund Full $${Number(it.amount).toLocaleString()}`}
                  </button>
                  {amt && (
                    <button data-testid={`refund-partial-${it.id}`} disabled={busy} onClick={() => doRefund(it, false)} className="btn-ghost !py-2 !text-xs">
                      Refund ${Number(amt).toLocaleString()}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
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
