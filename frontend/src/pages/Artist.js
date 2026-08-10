import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl, ORIGIN } from "../api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Plus, Gavel } from "lucide-react";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export function ArtistDashboard() {
  const { user, refresh } = useAuth();
  const [data, setData] = useState(null);
  const [artworks, setArtworks] = useState([]);
  const [profileOpen, setProfileOpen] = useState(false);
  const [bio, setBio] = useState(user?.bio || "");

  const load = () => {
    api.get("/artist/dashboard").then((r) => setData(r.data));
    api.get("/artworks/mine").then((r) => setArtworks(r.data));
  };
  useEffect(load, []);

  const startConnect = async () => {
    const r = await api.post("/artist/connect/start");
    window.open(r.data.onboarding_url, "_blank");
  };
  const completeConnect = async () => {
    await api.post("/artist/connect/complete"); await refresh(); load();
    toast.success("Stripe Connect linked");
  };
  const saveProfile = async () => {
    await api.patch("/auth/me", { bio });
    await refresh(); setProfileOpen(false); toast.success("Profile saved");
  };
  const payFee = async (id) => {
    try {
      const r = await api.post("/payments/upload-fee", { artwork_id: id, origin_url: ORIGIN });
      if (r.data.free) { toast.success("Live!"); load(); return; }
      window.location.href = r.data.checkout_url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const submitAotw = async (id) => {
    try { await api.post(`/artworks/${id}/submit-aotw`); toast.success("Submitted"); load(); }
    catch { toast.error("Only live artworks can be submitted"); }
  };

  if (!data) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;

  return (
    <div data-testid="artist-dashboard" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="flex flex-wrap items-end justify-between mb-12 gap-6">
        <div>
          <div className="label-caps text-[#CCFF00]">Studio</div>
          <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4">Hey, {user?.name}.</h1>
        </div>
        <div className="flex gap-3 flex-wrap">
          <button data-testid="edit-profile" onClick={() => setProfileOpen(!profileOpen)} className="btn-ghost">Edit Profile</button>
          <Link data-testid="new-auction-btn" to="/auctions/new" className="btn-violet"><Gavel size={14} className="mr-2" /> Launch Auction</Link>
          <Link data-testid="new-artwork-btn" to="/studio/upload" className="btn-lime"><Plus size={14} className="mr-2" /> New Artwork</Link>
        </div>
      </div>

      {profileOpen && (
        <div className="glass-card p-8 mb-12 rounded-sm">
          <div className="label-caps mb-3">Bio</div>
          <textarea data-testid="bio-input" value={bio} onChange={(e) => setBio(e.target.value)} rows={4}
            className="w-full bg-transparent border border-white/15 p-3 outline-none focus:border-[#CCFF00] rounded-sm" />
          <button data-testid="save-profile" onClick={saveProfile} className="btn-lime mt-4">Save</button>
        </div>
      )}

      <div className="grid md:grid-cols-4 gap-4 mb-16">
        <Stat label="Live listings" value={data.listings.live} accent="#FFFFFF" />
        <Stat label="Sold" value={data.listings.sold} accent="#CCFF00" />
        <Stat label="Pending fee" value={data.listings.pending_fee} accent="#FF4D4D" />
        <Stat label="Net earnings" value={`$${data.total_net.toLocaleString()}`} accent="#7C3AED" />
      </div>

      <div className="glass-card p-8 mb-16 rounded-sm">
        <div className="label-caps">Payouts (Stripe Connect)</div>
        <div className="mt-2 text-sm text-zinc-300">Status: <span className="text-[#CCFF00]" data-testid="connect-status">{data.stripe_connect_status}</span></div>
        <div className="flex flex-wrap gap-3 mt-6">
          {data.stripe_connect_status !== "connected" ? (
            <>
              <button data-testid="connect-start" onClick={startConnect} className="btn-lime">Start Onboarding</button>
              <button data-testid="connect-complete" onClick={completeConnect} className="btn-ghost">I've Completed It</button>
            </>
          ) : <div className="text-[#CCFF00] font-unbounded">Ready for payouts.</div>}
        </div>
      </div>

      <div className="label-caps mb-6">Your Artworks</div>
      {artworks.length === 0 ? (
        <div className="text-zinc-500 py-16 label-caps text-center border border-dashed border-white/10 rounded-sm">No artworks yet. <Link to="/studio/upload" className="text-[#CCFF00] ml-2">Upload your first →</Link></div>
      ) : (
        <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
          {artworks.map((a) => (
            <div key={a.id} data-testid={`my-art-${a.id}`} className="p-4 flex flex-wrap items-center gap-4">
              <img src={resolveImg(a.images?.[0])} className="w-16 h-16 object-cover rounded-sm" alt="" />
              <div className="flex-1 min-w-[200px]">
                <div className="font-unbounded text-lg font-semibold">{a.title}</div>
                <div className="label-caps mt-1">${Number(a.price).toLocaleString()} · <span className={
                  a.status === "live" ? "text-[#CCFF00]" : a.status === "sold" ? "text-[#7C3AED]" : "text-[#FF4D4D]"
                }>{a.status}</span></div>
              </div>
              {a.status === "pending_fee" && <button data-testid={`pay-fee-${a.id}`} onClick={() => payFee(a.id)} className="btn-lime">Pay Fee to List</button>}
              {a.status === "live" && !a.aotw_submitted && <button data-testid={`submit-aotw-${a.id}`} onClick={() => submitAotw(a.id)} className="btn-ghost">Submit Feature</button>}
              {a.aotw && <div className="badge-lime">Featured ★</div>}
              <Link to={`/artwork/${a.id}`} className="label-caps hover:text-[#CCFF00]">View</Link>
            </div>
          ))}
        </div>
      )}

      <div className="mt-16">
        <div className="label-caps mb-4">Recent Payouts</div>
        {data.payouts.length === 0 ? <div className="text-zinc-500 label-caps">No payouts yet.</div> : (
          <div className="border border-white/8 divide-y divide-white/8 text-sm rounded-sm">
            {data.payouts.slice(0, 10).map((p, i) => (
              <div key={i} className="p-4 flex justify-between items-center">
                <div className="text-zinc-400">{new Date(p.created_at).toLocaleDateString()}</div>
                <div className="font-anton text-xl">${p.net.toFixed(2)} <span className="text-zinc-500 text-xs font-manrope">of ${p.gross.toFixed(2)}</span></div>
                <div className="label-caps text-[#CCFF00]">{p.status}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div className="glass-card p-5 rounded-sm">
      <div className="label-caps">{label}</div>
      <div className="font-anton text-4xl mt-3" style={{ color: accent }}>{value}</div>
    </div>
  );
}

export function UploadArtwork() {
  const [form, setForm] = useState({ title: "", description: "", medium: "Oil", style: "", color: "", width_in: 12, height_in: 12, price: 100 });
  const [images, setImages] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [settings, setSettings] = useState(null);
  useEffect(() => { api.get("/settings").then((r) => setSettings(r.data)); }, []);

  const upload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setUploading(true);
    try {
      for (const f of files) {
        const fd = new FormData(); fd.append("file", f);
        const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
        setImages((prev) => [...prev, r.data.path]);
      }
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (images.length === 0) { toast.error("Add at least one image"); return; }
    try {
      const r = await api.post("/artworks", { ...form, images, price: Number(form.price), width_in: Number(form.width_in), height_in: Number(form.height_in) });
      toast.success("Artwork saved as draft");
      const fee = settings?.upload_fee ?? 0;
      if (fee > 0) {
        const p = await api.post("/payments/upload-fee", { artwork_id: r.data.id, origin_url: ORIGIN });
        window.location.href = p.data.checkout_url;
      } else {
        window.location.href = "/studio";
      }
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  return (
    <div data-testid="upload-artwork" className="max-w-3xl mx-auto px-6 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]">Upload</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4 mb-4">New Artwork</h1>
      <p className="text-zinc-400 mb-12">Listing fee: <span className="text-[#CCFF00] font-unbounded">${settings?.upload_fee ?? "..."}</span> — paid after saving.</p>
      <form onSubmit={submit} className="space-y-6">
        <Field label="Title"><input data-testid="art-title" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" /></Field>
        <Field label="Description"><textarea data-testid="art-description" required rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 focus:border-[#CCFF00] outline-none" /></Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Medium">
            <select data-testid="art-medium" value={form.medium} onChange={(e) => setForm({ ...form, medium: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm py-3 px-3">
              {["Oil", "Acrylic", "Watercolor", "Mixed Media", "Digital", "Photography"].map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </Field>
          <Field label="Style (optional)"><input data-testid="art-style" value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" /></Field>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Field label="Width (in)"><input data-testid="art-width" type="number" step="0.1" required value={form.width_in} onChange={(e) => setForm({ ...form, width_in: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
          <Field label="Height (in)"><input data-testid="art-height" type="number" step="0.1" required value={form.height_in} onChange={(e) => setForm({ ...form, height_in: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
          <Field label="Price (USD)"><input data-testid="art-price" type="number" min="1" required value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
        </div>
        <Field label="Images">
          <input data-testid="art-images" type="file" accept="image/*" multiple onChange={upload} className="text-sm" />
          {uploading && <div className="text-xs text-[#CCFF00] mt-2">Uploading...</div>}
          <div className="flex flex-wrap gap-3 mt-4">
            {images.map((p) => <img key={p} src={fileUrl(p)} className="w-24 h-24 object-cover rounded-sm border border-white/8" alt="" />)}
          </div>
        </Field>
        <button data-testid="submit-artwork" className="btn-lime mt-6">Save & Continue</button>
      </form>
    </div>
  );
}

function Field({ label, children }) {
  return <label className="block"><div className="label-caps mb-2">{label}</div>{children}</label>;
}
