import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl, ORIGIN } from "../api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Plus, Gavel } from "lucide-react";
import { ListingAssistant } from "../components/studio/ListingAssistant";

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
  const [form, setForm] = useState({
    title: "", description: "", medium: "Oil", style: "", color: "",
    width_in: 12, height_in: 12, price: 100,
    year: new Date().getFullYear(), category: "", tags: "",
    quantity: 1, kind: "original", shipping_info: "", coa: "",
    section: new URLSearchParams(window.location.search).get("section") === "upcycle" ? "upcycle" : "art", furniture_type: "chair", materials: "", before_image: null, delivery: ["ships"], loc_city: "", loc_lat: "", loc_lng: "",
  });
  const [images, setImages] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [settings, setSettings] = useState(null);
  useEffect(() => { api.get("/settings").then((r) => setSettings(r.data)); }, []);

  const geocodeCity = async () => {
    if (!form.loc_city.trim()) return toast.error("Enter your city first");
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(form.loc_city)}`, { headers: { Accept: "application/json" } });
      const d = await r.json();
      if (d?.[0]) { setForm((x) => ({ ...x, loc_lat: parseFloat(d[0].lat).toFixed(5), loc_lng: parseFloat(d[0].lon).toFixed(5) })); toast.success("Location set"); }
      else toast.error("City not found");
    } catch { toast.error("Lookup failed"); }
  };
  const toggleDelivery = (k) => setForm((x) => { const has = x.delivery.includes(k); const next = has ? x.delivery.filter((d) => d !== k) : [...x.delivery, k]; return { ...x, delivery: next.length ? next : x.delivery }; });

  const uploadBefore = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    try { const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } }); setForm((x) => ({ ...x, before_image: r.data.path })); }
    catch { toast.error("Upload failed"); }
  };

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
  const removeImg = (p) => setImages((prev) => prev.filter((x) => x !== p));

  const submit = async (e) => {
    e.preventDefault();
    if (images.length === 0) { toast.error("Add at least one image"); return; }
    try {
      const payload = {
        ...form, images,
        price: Number(form.price),
        width_in: Number(form.width_in), height_in: Number(form.height_in),
        year: form.year ? Number(form.year) : null,
        quantity: Number(form.quantity) || 1,
        tags: form.tags ? form.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
        furniture_type: form.section === "upcycle" ? form.furniture_type : null,
        materials: form.section === "upcycle" ? form.materials || null : null,
        before_image: form.section === "upcycle" ? form.before_image : null,
        delivery: form.delivery,
        location: form.loc_lat && form.loc_lng ? { lat: Number(form.loc_lat), lng: Number(form.loc_lng), city: form.loc_city || null } : null,
      };
      const r = await api.post("/artworks", payload);
      toast.success("Artwork saved");
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
      <p className="text-zinc-400 mb-12">Listing fee: <span className="text-[#CCFF00] font-unbounded">${settings?.upload_fee ?? "..."}</span></p>
      <form onSubmit={submit} className="space-y-6">
        {images.length === 0 && <div className="text-xs text-zinc-500 border border-dashed border-white/10 rounded-sm p-3" data-testid="assist-tip">Tip: add your photo first (bottom of the form) and the <span className="text-[#7C3AED]">Listing assistant</span> can draft the title, description, tags and price for you.</div>}
        <Field label="Title"><input data-testid="art-title" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" /></Field>
        <Field label="Description"><textarea data-testid="art-description" required rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 focus:border-[#CCFF00] outline-none" /></Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Medium">
            <select data-testid="art-medium" value={form.medium} onChange={(e) => setForm({ ...form, medium: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm py-3 px-3">
              {["Oil", "Acrylic", "Watercolor", "Mixed Media", "Digital", "Photography", "Sculpture", "Print"].map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </Field>
          <Field label="Section">
            <select data-testid="art-section" value={form.section} onChange={(e) => setForm({ ...form, section: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm py-3 px-3">
              <option value="art">Art</option>
              <option value="upcycle">Upcycle (furniture as art)</option>
            </select>
          </Field>
          <Field label="Type">
            <select data-testid="art-kind" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm py-3 px-3">
              <option value="original">Original</option>
              <option value="print">Print</option>
              <option value="digital">Digital</option>
            </select>
          </Field>
        </div>
        {form.section === "upcycle" && (
          <div className="grid md:grid-cols-3 gap-4 border border-[#34D399]/30 rounded-sm p-4" data-testid="upcycle-fields">
            <Field label="Furniture type">
              <select data-testid="art-furniture-type" value={form.furniture_type} onChange={(e) => setForm({ ...form, furniture_type: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm py-3 px-3">
                {["chair", "table", "dresser", "cabinet", "lamp", "mirror", "shelf", "bench", "other"].map((t) => <option key={t} value={t}>{t[0].toUpperCase() + t.slice(1)}</option>)}
              </select>
            </Field>
            <Field label="Materials & finish">
              <input data-testid="art-materials" value={form.materials} onChange={(e) => setForm({ ...form, materials: e.target.value })} placeholder="Reclaimed oak, spray paint, 2K clear coat" className="w-full bg-white/[0.03] border border-white/12 rounded-sm py-3 px-3" />
            </Field>
            <Field label="Delivery (eBay-style — you handle shipping)">
              <div className="flex gap-2">
                {[["ships", "I'll ship it"], ["local_pickup", "Local pickup"]].map(([k, l]) => (
                  <button type="button" key={k} data-testid={`art-delivery-${k}`} onClick={() => toggleDelivery(k)} className={`flex-1 label-caps text-[10px] px-2 py-3 rounded-sm border ${form.delivery.includes(k) ? "border-[#34D399] text-[#34D399] bg-[#34D399]/10" : "border-white/12 text-zinc-500"}`}>{l}</button>
                ))}
              </div>
            </Field>
            <Field label="Piece location (for 'near me')">
              <div className="flex gap-2">
                <input data-testid="art-loc-city" value={form.loc_city} onChange={(e) => setForm({ ...form, loc_city: e.target.value })} placeholder="City, State" className="flex-1 min-w-0 bg-white/[0.03] border border-white/12 rounded-sm py-3 px-3" />
                <button type="button" data-testid="art-loc-find" onClick={geocodeCity} className="btn-ghost !py-2 !px-3 text-xs">{form.loc_lat ? "✓" : "Find"}</button>
              </div>
            </Field>
            <Field label="Before photo (optional)">
              <label className="btn-ghost !py-3 cursor-pointer flex items-center justify-center text-xs">{form.before_image ? "Before photo added ✓" : "Upload the 'before'"}
                <input data-testid="art-before-image" type="file" accept="image/*" className="hidden" onChange={uploadBefore} /></label>
            </Field>
          </div>
        )}
        <div className="grid grid-cols-2 gap-4">
          <Field label="Style (optional)"><input data-testid="art-style" value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
          <Field label="Category (optional)"><input data-testid="art-category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="Portrait, Landscape..." className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Field label="Width (in)"><input data-testid="art-width" type="number" step="0.1" required value={form.width_in} onChange={(e) => setForm({ ...form, width_in: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
          <Field label="Height (in)"><input data-testid="art-height" type="number" step="0.1" required value={form.height_in} onChange={(e) => setForm({ ...form, height_in: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
          <Field label="Year"><input data-testid="art-year" type="number" min="1900" max={new Date().getFullYear()} value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Price (USD)"><input data-testid="art-price" type="number" min="1" required value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
          <Field label="Quantity"><input data-testid="art-quantity" type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
        </div>
        <Field label="Tags (comma separated)"><input data-testid="art-tags" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="neon, urban, portrait" className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none" /></Field>
        <Field label="Shipping info (optional)"><textarea data-testid="art-shipping" rows={2} value={form.shipping_info} onChange={(e) => setForm({ ...form, shipping_info: e.target.value })} placeholder="Ships worldwide within 5 business days..." className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none" /></Field>
        <Field label="Certificate of Authenticity (optional)"><textarea data-testid="art-coa" rows={2} value={form.coa} onChange={(e) => setForm({ ...form, coa: e.target.value })} placeholder="Signed COA included with delivery..." className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none" /></Field>
        <Field label="Images (drag to reorder later)">
          <input data-testid="art-images" type="file" accept="image/*" multiple onChange={upload} className="text-sm" />
          {uploading && <div className="text-xs text-[#CCFF00] mt-2">Uploading...</div>}
          <div className="flex flex-wrap gap-3 mt-4">
            {images.map((p) => (
              <div key={p} className="relative group">
                <img src={fileUrl(p)} className="w-24 h-24 object-cover rounded-sm border border-white/8" alt="" />
                <button type="button" onClick={() => removeImg(p)} className="absolute -top-2 -right-2 bg-[#FF4D4D] text-white w-5 h-5 rounded-full text-xs opacity-0 group-hover:opacity-100">×</button>
              </div>
            ))}
          </div>
        </Field>
        <ListingAssistant imagePath={images[0]} form={form} onApply={(patch) => setForm((x) => ({ ...x, ...patch }))} />
        <button data-testid="submit-artwork" className="btn-lime mt-6">Save & Continue</button>
      </form>
    </div>
  );
}

function Field({ label, children }) {
  return <label className="block"><div className="label-caps mb-2">{label}</div>{children}</label>;
}
