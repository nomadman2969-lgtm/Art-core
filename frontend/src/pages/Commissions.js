import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, fileUrl, ORIGIN } from "../api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Palette, Check, X, RefreshCw, Upload, Package, CreditCard } from "lucide-react";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

const STATUS_STYLES = {
  pending: { color: "#F5A623", label: "Pending" },
  accepted: { color: "#CCFF00", label: "Accepted" },
  in_progress: { color: "#7C3AED", label: "In Progress" },
  counter: { color: "#F5A623", label: "Counter Offer" },
  declined: { color: "#FF4D4D", label: "Declined" },
  delivered: { color: "#00E5FF", label: "Delivered" },
  approved: { color: "#CCFF00", label: "Approved · Payment Due" },
  paid: { color: "#CCFF00", label: "Paid" },
  cancelled: { color: "#52525B", label: "Cancelled" },
};

export function CommissionsInbox() {
  const { user } = useAuth();
  const [tab, setTab] = useState(user?.role === "artist" || user?.role === "admin" ? "artist" : "buyer");
  const [items, setItems] = useState([]);
  const load = () => api.get(`/commissions/mine?as_role=${tab}`).then((r) => setItems(r.data));
  useEffect(() => { load(); }, [tab]);

  return (
    <div data-testid="commissions-inbox" className="max-w-[1200px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]"><Palette size={12} className="inline mr-2" /> Commissions</div>
      <h1 className="font-anton text-5xl md:text-8xl uppercase mt-4 mb-10">Custom Work</h1>

      <div className="flex gap-1 border-b border-white/8 mb-8">
        <button data-testid="tab-buyer" onClick={() => setTab("buyer")}
          className={`label-caps px-4 py-3 border-b-2 ${tab === "buyer" ? "border-[#CCFF00] text-white" : "border-transparent text-zinc-500"}`}>
          Requests I've sent
        </button>
        {(user?.role === "artist" || user?.role === "admin") && (
          <button data-testid="tab-artist" onClick={() => setTab("artist")}
            className={`label-caps px-4 py-3 border-b-2 ${tab === "artist" ? "border-[#CCFF00] text-white" : "border-transparent text-zinc-500"}`}>
            Requests I've received
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="border border-dashed border-white/10 py-24 text-center rounded-sm">
          <div className="label-caps text-zinc-500">
            {tab === "buyer" ? "No commission requests yet." : "No incoming requests yet."}
          </div>
          {tab === "buyer" && <div className="text-sm text-zinc-400 mt-4">Visit an <Link to="/artists" className="text-[#CCFF00]">artist portfolio</Link> to request a custom piece.</div>}
        </div>
      ) : (
        <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
          {items.map((c) => {
            const s = STATUS_STYLES[c.status] || STATUS_STYLES.pending;
            return (
              <Link key={c.id} to={`/commissions/${c.id}`} data-testid={`commission-row-${c.id}`}
                className="p-5 flex flex-wrap items-center gap-4 hover:bg-white/[0.03] transition-colors">
                <div className="flex-1 min-w-[200px]">
                  <div className="font-unbounded font-semibold text-lg">{c.kind === "flip" && <span className="label-caps text-[10px] text-[#34D399] mr-2">Flip</span>}{c.subject}</div>
                  <div className="text-sm text-zinc-400 mt-1 line-clamp-1">{c.instructions}</div>
                  <div className="label-caps mt-2">
                    {tab === "buyer" ? `To ${c.artist?.name}` : `From ${c.buyer?.name}`} · {new Date(c.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-anton text-2xl text-[#CCFF00]">${Number(c.counter_amount || c.budget).toLocaleString()}</div>
                  <div className="badge-violet mt-2" style={{ background: `${s.color}20`, color: s.color, border: `1px solid ${s.color}60` }}>{s.label}</div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function CommissionCreate() {
  const { artistId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [artist, setArtist] = useState(null);
  const [refs, setRefs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [form, setForm] = useState({ subject: "", style: "", size: "", budget: 500, deadline: "", instructions: "" });

  useEffect(() => {
    api.get(`/artists/${artistId}`).then((r) => setArtist(r.data));
  }, [artistId]);

  const upload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    try {
      for (const f of files) {
        const fd = new FormData(); fd.append("file", f);
        const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
        setRefs((prev) => [...prev, r.data.path]);
      }
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!user) { toast("Sign in"); return; }
    try {
      const r = await api.post("/commissions", {
        artist_id: artistId, ...form,
        budget: Number(form.budget), reference_images: refs,
        deadline: form.deadline || null,
      });
      toast.success("Request sent");
      nav(`/commissions/${r.data.id}`);
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
  };

  if (!artist) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;
  return (
    <div data-testid="commission-create" className="max-w-2xl mx-auto px-6 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]">Request a Commission</div>
      <h1 className="font-anton text-5xl uppercase mt-4">Commission {artist.name}</h1>
      <p className="text-zinc-400 mt-2">Describe what you want. {artist.name} can accept, decline, or counter your offer.</p>
      <form onSubmit={submit} className="space-y-5 mt-10">
        <Field label="Subject / Title"><input data-testid="c-subject" required value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none focus:border-[#CCFF00]" /></Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Style"><input data-testid="c-style" value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none" /></Field>
          <Field label="Size (e.g. 24x36 in)"><input data-testid="c-size" value={form.size} onChange={(e) => setForm({ ...form, size: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none" /></Field>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Budget (USD)"><input data-testid="c-budget" type="number" min="1" required value={form.budget} onChange={(e) => setForm({ ...form, budget: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none" /></Field>
          <Field label="Deadline (optional)"><input data-testid="c-deadline" type="date" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none" /></Field>
        </div>
        <Field label="Instructions"><textarea data-testid="c-instructions" required rows={5} value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none focus:border-[#CCFF00]" /></Field>
        <Field label="Reference images (optional)">
          <input data-testid="c-refs" type="file" accept="image/*" multiple onChange={upload} className="text-sm" />
          {uploading && <div className="text-xs text-[#CCFF00] mt-2">Uploading...</div>}
          <div className="flex flex-wrap gap-3 mt-3">
            {refs.map((p) => <img key={p} src={fileUrl(p)} className="w-20 h-20 object-cover rounded-sm border border-white/8" alt="" />)}
          </div>
        </Field>
        <button data-testid="c-submit" className="btn-lime">Send Request</button>
      </form>
    </div>
  );
}

function Field({ label, children }) {
  return <label className="block"><div className="label-caps mb-2">{label}</div>{children}</label>;
}

export function CommissionDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [c, setC] = useState(null);
  const [counter, setCounter] = useState("");
  const [progressMsg, setProgressMsg] = useState("");
  const [deliverFiles, setDeliverFiles] = useState([]);
  const [deliverMsg, setDeliverMsg] = useState("");
  const [uploading, setUploading] = useState(false);

  const load = () => api.get(`/commissions/${id}`).then((r) => setC(r.data)).catch(() => nav("/commissions"));
  useEffect(() => { load(); }, [id]);

  if (!c) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;

  const isArtist = user?.id === c.artist_id;
  const isBuyer = user?.id === c.buyer_id;
  const s = STATUS_STYLES[c.status] || STATUS_STYLES.pending;

  const respond = async (action, extra = {}) => {
    try {
      await api.post(`/commissions/${id}/respond`, { action, ...extra });
      toast.success("Sent");
      load();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
  };
  const buyerAction = async (action) => {
    try {
      await api.post(`/commissions/${id}/buyer-action`, { action });
      toast.success("Sent"); load();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
  };
  const addProgress = async () => {
    if (!progressMsg.trim()) return;
    try {
      await api.post(`/commissions/${id}/progress`, { message: progressMsg });
      setProgressMsg(""); toast.success("Progress added"); load();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
  };
  const upload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    try {
      for (const f of files) {
        const fd = new FormData(); fd.append("file", f);
        const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
        setDeliverFiles((prev) => [...prev, r.data.path]);
      }
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };
  const deliver = async () => {
    if (deliverFiles.length === 0) { toast.error("Attach at least one final image"); return; }
    try {
      await api.post(`/commissions/${id}/deliver`, { message: deliverMsg, final_images: deliverFiles });
      toast.success("Delivered"); setDeliverFiles([]); setDeliverMsg(""); load();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
  };
  const approve = async () => {
    try {
      await api.post(`/commissions/${id}/approve`);
      toast.success("Approved"); load();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
  };

  return (
    <div data-testid="commission-detail" className="max-w-4xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <button onClick={() => nav("/commissions")} className="label-caps text-zinc-500 hover:text-[#CCFF00] mb-6">← All commissions</button>
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="label-caps text-[#CCFF00]">Commission · <span style={{ color: s.color }}>{s.label}</span></div>
          <h1 className="font-anton text-4xl md:text-6xl uppercase mt-3">{c.subject}</h1>
          <div className="text-sm text-zinc-400 mt-2">
            <Link to={`/artist/${c.artist_id}`} className="text-[#CCFF00]">{c.artist?.name}</Link>
            {" ← "}
            <span>{c.buyer?.name}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="label-caps">Budget</div>
          <div className="font-anton text-4xl text-[#CCFF00]">${Number(c.counter_amount || c.budget).toLocaleString()}</div>
        </div>
      </div>

      {c.kind === "flip" && c.furniture && (
        <div className="mt-8 border border-[#34D399]/30 bg-[#34D399]/5 rounded-sm p-5" data-testid="flip-details">
          <div className="label-caps text-[#34D399] mb-3">Furniture flip · collector's own piece</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><div className="label-caps text-zinc-500 text-[10px]">Piece</div><div className="capitalize mt-1">{c.furniture.furniture_type}</div></div>
            <div><div className="label-caps text-zinc-500 text-[10px]">Condition</div><div className="capitalize mt-1">{c.furniture.condition || "—"}</div></div>
            <div><div className="label-caps text-zinc-500 text-[10px]">Dimensions</div><div className="mt-1">{c.furniture.dimensions || "—"}</div></div>
            <div><div className="label-caps text-zinc-500 text-[10px]">Hand-off</div><div className="mt-1">{{ dropoff: "Collector drops off", pickup: "Artist picks up", ship: "Collector ships" }[c.furniture.handoff] || c.furniture.handoff}{c.furniture.city ? ` · ${c.furniture.city}` : ""}</div></div>
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-4 mt-10">
        <Meta label="Style" value={c.style || "—"} />
        <Meta label="Size" value={c.size || "—"} />
        <Meta label="Deadline" value={c.deadline ? new Date(c.deadline).toLocaleDateString() : "Flexible"} />
      </div>

      <div className="mt-10 border border-white/8 rounded-sm p-6">
        <div className="label-caps mb-4">Brief</div>
        <p className="text-zinc-200 whitespace-pre-wrap">{c.instructions}</p>
      </div>

      <CommissionTimeline c={c} />

      {c.reference_images?.length > 0 && (
        <div className="mt-6">
          <div className="label-caps mb-3">Reference images</div>
          <div className="flex flex-wrap gap-3">
            {c.reference_images.map((p) => <img key={p} src={resolveImg(p)} className="w-32 h-32 object-cover rounded-sm border border-white/8" alt="" />)}
          </div>
        </div>
      )}

      {/* Action panels based on role + status */}
      {isArtist && c.status === "pending" && (
        <div className="mt-8 glass-card p-6 rounded-sm space-y-4" data-testid="artist-respond-panel">
          <div className="label-caps text-[#CCFF00]">Your response</div>
          <div className="flex flex-wrap gap-3">
            <button data-testid="respond-accept" onClick={() => respond("accept")} className="btn-lime"><Check size={14} className="mr-2" /> Accept ${Number(c.budget).toLocaleString()}</button>
            <button data-testid="respond-decline" onClick={() => respond("decline")} className="btn-ghost"><X size={14} className="mr-2" /> Decline</button>
          </div>
          <div className="border-t border-white/8 pt-4">
            <div className="label-caps mb-2">Counter offer</div>
            <div className="flex gap-2">
              <input data-testid="counter-input" type="number" min="1" value={counter} onChange={(e) => setCounter(e.target.value)} placeholder="Amount" className="flex-1 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none" />
              <button data-testid="respond-counter" disabled={!counter} onClick={() => respond("counter", { counter_amount: Number(counter) })} className="btn-violet"><RefreshCw size={14} className="mr-2" /> Send Counter</button>
            </div>
          </div>
        </div>
      )}

      {isBuyer && c.status === "counter" && (
        <div className="mt-8 glass-card p-6 rounded-sm" data-testid="buyer-counter-panel">
          <div className="label-caps text-[#F5A623]">Counter offer received</div>
          <div className="font-anton text-3xl text-[#CCFF00] mt-2">${Number(c.counter_amount).toLocaleString()}</div>
          <div className="flex gap-3 mt-4">
            <button data-testid="accept-counter" onClick={() => buyerAction("accept_counter")} className="btn-lime">Accept Counter</button>
            <button data-testid="cancel-commission" onClick={() => buyerAction("cancel")} className="btn-ghost">Cancel</button>
          </div>
        </div>
      )}

      {isArtist && c.status === "in_progress" && (
        <div className="mt-8 glass-card p-6 rounded-sm space-y-6" data-testid="artist-progress-panel">
          {c.deposit_paid && (
            <div className="badge-lime !text-xs" data-testid="deposit-paid">Deposit received · ${Number(c.deposit_amount).toLocaleString()}</div>
          )}
          <div>
            <div className="label-caps mb-2">Post a progress update</div>
            <div className="flex gap-2">
              <input data-testid="progress-input" value={progressMsg} onChange={(e) => setProgressMsg(e.target.value)} placeholder="Sketch done, moving to color..." className="flex-1 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none" />
              <button data-testid="progress-submit" onClick={addProgress} className="btn-ghost">Post</button>
            </div>
          </div>
          <div className="border-t border-white/8 pt-6">
            <div className="label-caps mb-3"><Package size={12} className="inline mr-2" /> Deliver final work</div>
            <input data-testid="deliver-files" type="file" accept="image/*" multiple onChange={upload} className="text-sm" />
            {uploading && <div className="text-xs text-[#CCFF00] mt-2">Uploading...</div>}
            <div className="flex flex-wrap gap-3 mt-3">
              {deliverFiles.map((p) => <img key={p} src={fileUrl(p)} className="w-20 h-20 object-cover rounded-sm" alt="" />)}
            </div>
            <textarea data-testid="deliver-message" value={deliverMsg} onChange={(e) => setDeliverMsg(e.target.value)} rows={2} placeholder="Delivery notes..." className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 mt-3 outline-none" />
            <button data-testid="deliver-submit" onClick={deliver} className="btn-lime mt-3"><Upload size={14} className="mr-2" /> Deliver</button>
          </div>
        </div>
      )}

      {isBuyer && c.status === "in_progress" && !c.deposit_paid && (
        <div className="mt-8 glass-card p-6 rounded-sm" data-testid="buyer-deposit-panel">
          <div className="label-caps text-[#F5A623]">Deposit required to lock in the artist</div>
          <div className="font-anton text-3xl mt-2">50% up front</div>
          <div className="text-sm text-zinc-400 mt-2">Pay a deposit now to secure the commission. The remaining balance is due after you approve delivery.</div>
          <PayDepositButton commissionId={c.id} total={c.counter_amount || c.budget} onDone={load} />
        </div>
      )}

      {isBuyer && c.status === "in_progress" && c.deposit_paid && (
        <div className="mt-8 border border-white/10 p-4 rounded-sm" data-testid="deposit-confirmed">
          <div className="label-caps text-[#CCFF00]">Deposit paid · ${Number(c.deposit_amount).toLocaleString()}</div>
          <div className="text-sm text-zinc-400 mt-2">Balance ${Number((c.counter_amount || c.budget) - c.deposit_amount).toLocaleString()} due after delivery is approved.</div>
        </div>
      )}

      {isBuyer && c.status === "delivered" && (
        <div className="mt-8 glass-card p-6 rounded-sm" data-testid="buyer-approve-panel">
          <div className="label-caps text-[#00E5FF]">Final work delivered</div>
          <div className="flex flex-wrap gap-3 mt-4">
            {c.final_images.map((p) => <img key={p} src={resolveImg(p)} className="w-32 h-32 object-cover rounded-sm border border-white/8" alt="" />)}
          </div>
          <button data-testid="approve-delivery" onClick={approve} className="btn-lime mt-4">Approve Delivery</button>
        </div>
      )}

      {isBuyer && c.status === "approved" && !c.paid && (
        <div className="mt-8 glass-card p-6 rounded-sm" data-testid="buyer-pay-panel">
          <div className="label-caps text-[#CCFF00]">Payment due</div>
          <div className="font-anton text-4xl text-[#CCFF00] mt-2">${Number(c.counter_amount || c.budget).toLocaleString()}</div>
          <div className="text-sm text-zinc-400 mt-3">You've approved the delivery. Complete payment to release funds to {c.artist?.name}.</div>
          <PayCommissionButton commissionId={c.id} amount={c.counter_amount || c.budget} />
        </div>
      )}

      {(c.status === "paid" || c.paid) && (
        <div className="mt-8 glass-card p-6 rounded-sm" data-testid="commission-paid-panel">
          <div className="badge-lime">Paid</div>
          <div className="text-sm mt-3 text-zinc-200">Payment settled. Funds released to {c.artist?.name}.</div>
        </div>
      )}

      {/* Progress log */}
      <div className="mt-10">
        <div className="label-caps mb-6">Activity</div>
        {c.progress?.length === 0 ? <div className="text-zinc-500 text-sm">No activity yet.</div> : (
          <div className="border-l-2 border-white/8 pl-6 space-y-6">
            {c.progress?.map((p, i) => (
              <div key={i} data-testid={`progress-${i}`} className="relative">
                <div className="absolute -left-[29px] w-3 h-3 bg-[#CCFF00] rounded-full top-1.5" />
                <div className="label-caps">{p.kind?.replace(/_/g, " ")} · {new Date(p.at).toLocaleString()}</div>
                {p.message && <div className="text-zinc-200 mt-1">{p.message}</div>}
                {p.image && <img src={resolveImg(p.image)} className="w-32 h-32 object-cover rounded-sm mt-3" alt="" />}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Meta({ label, value }) {
  return <div className="glass-card p-4 rounded-sm"><div className="label-caps">{label}</div><div className="font-unbounded text-sm mt-2">{value}</div></div>;
}

function PayCommissionButton({ commissionId, amount }) {
  const [busy, setBusy] = React.useState(false);
  const pay = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/payments/commissions/${commissionId}/pay`, { origin_url: ORIGIN });
      window.location.href = r.data.checkout_url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Payment failed"); setBusy(false); }
  };
  return (
    <button data-testid="pay-commission-btn" onClick={pay} disabled={busy} className="btn-lime mt-4">
      <CreditCard size={14} className="mr-2" />
      {busy ? "Redirecting..." : `Pay $${Number(amount).toLocaleString()}`}
    </button>
  );
}

function PayDepositButton({ commissionId, total, onDone }) {
  const [busy, setBusy] = React.useState(false);
  const pay = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/payments/commissions/${commissionId}/deposit`, { origin_url: ORIGIN });
      window.location.href = r.data.checkout_url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); setBusy(false); }
  };
  const deposit = Math.round(Number(total) * 0.5);
  return (
    <button data-testid="pay-deposit-btn" onClick={pay} disabled={busy} className="btn-lime mt-4">
      <CreditCard size={14} className="mr-2" />
      {busy ? "Redirecting..." : `Pay Deposit $${deposit.toLocaleString()}`}
    </button>
  );
}


// ---------- Commission Escrow Timeline ----------
function CommissionTimeline({ c }) {
  const total = Number(c.counter_amount || c.budget || 0);
  const deposit = Math.round(total * 0.5);
  const balance = total - deposit;
  const platformPercent = Number(c.platform_take && total ? (c.platform_take / total) * 100 : 15);
  const netToArtist = Number(c.net_to_artist || (total * (1 - platformPercent / 100))).toFixed(0);

  // Find the earliest "at" for a given progress kind (or list of kinds)
  const findAt = (kinds) => {
    const set = Array.isArray(kinds) ? kinds : [kinds];
    const hit = (c.progress || []).find((p) => set.includes(p.kind));
    return hit?.at || null;
  };
  const fmt = (iso) => iso ? new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : null;

  // Build stages based on current status
  const responseAt = findAt(["artist_accept", "artist_counter", "artist_decline"]);
  const acceptedAt = findAt(["artist_accept", "buyer_accepted_counter"]);
  const deliveredAt = findAt("artist_delivered");
  const approvedAt = findAt("buyer_approved");
  const isDeclined = c.status === "declined";
  const isCancelled = c.status === "cancelled";

  const stages = [
    {
      key: "request",
      title: "Request submitted",
      caption: `${c.buyer?.name || "Buyer"} sent brief · Budget $${Number(c.budget).toLocaleString()}`,
      at: c.created_at,
      done: true,
    },
    {
      key: "response",
      title: isDeclined ? "Artist declined" : c.status === "counter" ? "Artist countered" : "Artist accepted",
      caption: c.counter_amount && c.status === "counter" ? `Counter offer: $${Number(c.counter_amount).toLocaleString()}` :
               acceptedAt ? `Terms agreed at $${total.toLocaleString()}` : "Waiting for artist's response",
      at: responseAt,
      done: !!responseAt,
      failed: isDeclined,
    },
    {
      key: "deposit",
      title: c.deposit_paid ? "Deposit paid · 50% held in escrow" : "Deposit due",
      caption: c.deposit_paid
        ? `$${deposit.toLocaleString()} secured by Art Core. Released to artist when work is approved.`
        : `Buyer pays $${deposit.toLocaleString()} to start work.`,
      at: c.deposit_paid_at,
      done: !!c.deposit_paid,
      pending: acceptedAt && !c.deposit_paid && !isDeclined && !isCancelled,
    },
    {
      key: "progress",
      title: "Work in progress",
      caption: (c.progress || []).filter((p) => p.kind === "artist_update").length
        ? `${(c.progress || []).filter((p) => p.kind === "artist_update").length} progress update(s) shared`
        : "Artist working — updates will appear here",
      at: c.deposit_paid ? c.deposit_paid_at : null,
      done: c.status === "delivered" || c.status === "approved" || c.status === "paid",
      pending: c.status === "in_progress" && c.deposit_paid,
    },
    {
      key: "delivered",
      title: "Final work delivered",
      caption: "Buyer reviews the final piece. Approval unlocks the balance payment.",
      at: deliveredAt,
      done: !!deliveredAt,
      pending: c.status === "in_progress" && c.deposit_paid,
    },
    {
      key: "approved",
      title: "Buyer approved",
      caption: "Balance payment unlocked — funds ready for release.",
      at: approvedAt,
      done: !!approvedAt,
      pending: c.status === "delivered",
    },
    {
      key: "paid",
      title: c.paid ? "Balance paid · Escrow released" : `Balance due · $${balance.toLocaleString()}`,
      caption: c.paid
        ? `Escrow released — artist receives $${netToArtist} net (Art Core keeps ${platformPercent.toFixed(0)}%).`
        : `Buyer pays remaining $${balance.toLocaleString()}. Funds transfer to artist on payment.`,
      at: c.paid_at,
      done: !!c.paid,
      pending: c.status === "approved" && !c.paid,
    },
  ];

  return (
    <div className="mt-8 glass-card p-6 md:p-8 rounded-sm" data-testid="commission-timeline">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="label-caps text-[#CCFF00]">Escrow Timeline</div>
          <div className="text-xs text-zinc-500 mt-1">Art Core holds payment in escrow to protect both sides.</div>
        </div>
        <div className="text-right">
          <div className="label-caps">Total</div>
          <div className="font-anton text-2xl">${total.toLocaleString()}</div>
        </div>
      </div>

      {/* Escrow allocation bar */}
      <div className="mb-8">
        <div className="flex items-center text-xs label-caps mb-2 justify-between">
          <span>Deposit ${deposit.toLocaleString()}</span>
          <span>Balance ${balance.toLocaleString()}</span>
        </div>
        <div className="flex h-2 rounded-full overflow-hidden bg-white/8">
          <div className="w-1/2 relative" style={{ background: c.deposit_paid ? "#CCFF00" : "rgba(255,255,255,0.15)" }} />
          <div className="w-1/2 relative" style={{ background: c.paid ? "#CCFF00" : "rgba(255,255,255,0.15)" }} />
        </div>
        <div className="flex items-center text-xs mt-2 justify-between text-zinc-500">
          <span>{c.deposit_paid ? "✓ Held in escrow" : "Pending"}</span>
          <span>{c.paid ? "✓ Released" : "Pending"}</span>
        </div>
      </div>

      {/* Vertical timeline */}
      <div className="relative">
        <div className="absolute left-3 top-2 bottom-2 w-px bg-white/8" />
        <div className="space-y-5">
          {stages.map((st) => (
            <TimelineNode key={st.key} stage={st} fmt={fmt} />
          ))}
        </div>
      </div>
    </div>
  );
}

function TimelineNode({ stage, fmt }) {
  const dot = stage.failed ? "#FF4D4D"
    : stage.done ? "#CCFF00"
    : stage.pending ? "#F5A623"
    : "#3F3F46";
  const textCls = stage.done ? "text-white" : stage.pending ? "text-zinc-100" : "text-zinc-500";
  return (
    <div className="relative pl-10" data-testid={`timeline-${stage.key}`}>
      <div className="absolute left-0 top-1 w-6 h-6 rounded-full border-2 flex items-center justify-center"
        style={{ borderColor: dot, background: stage.done ? dot : "#0A0A0C" }}>
        {stage.done && !stage.failed && <Check size={12} color="#0A0A0C" strokeWidth={4} />}
        {stage.failed && <X size={12} color={dot} strokeWidth={3} />}
        {stage.pending && !stage.done && (
          <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: dot }} />
        )}
      </div>
      <div className={`font-unbounded text-sm md:text-base font-semibold ${textCls}`}>{stage.title}</div>
      <div className="text-xs text-zinc-500 mt-1">{stage.caption}</div>
      {stage.at && <div className="label-caps mt-1 text-zinc-600">{fmt(stage.at)}</div>}
    </div>
  );
}
