import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Recycle, Hammer, Sparkles, ArrowRight, Navigation, X, MapPin, Truck } from "lucide-react";
import { toast } from "sonner";
import { api, thumbUrl } from "../api";
import { useAuth } from "../context/AuthContext";

export function BeforeAfter({ before, after, title, className = "" }) {
  const [showBefore, setShowBefore] = useState(false);
  if (!before) return <img src={thumbUrl(after, 960)} alt={title} className={`w-full h-full object-cover ${className}`} />;
  return (
    <div className={`relative w-full h-full group ${className}`} data-testid="before-after">
      <img src={thumbUrl(after, 960)} alt={title} className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-500 ${showBefore ? "opacity-0" : "opacity-100"}`} />
      <img src={thumbUrl(before, 960)} alt={`${title} — before`} className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-500 ${showBefore ? "opacity-100" : "opacity-0"}`} />
      <button type="button" data-testid="before-after-toggle" onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowBefore((v) => !v); }}
        className="absolute bottom-3 left-3 label-caps text-[10px] px-2.5 py-1.5 rounded-sm bg-black/70 backdrop-blur-md text-white border border-white/20 hover:border-[#CCFF00] hover:text-[#CCFF00]">
        {showBefore ? "Show after" : "Show before"}
      </button>
      <span className="absolute top-3 left-3 label-caps text-[10px] px-2 py-1 rounded-sm bg-black/60 backdrop-blur-md" style={{ color: showBefore ? "#A1A1AA" : "#CCFF00" }}>{showBefore ? "Before" : "After"}</span>
    </div>
  );
}

export default function Upcycle() {
  const { user } = useAuth();
  const [meta, setMeta] = useState({ types: [], total: 0 });
  const [type, setType] = useState("");
  const [sort, setSort] = useState("recent");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [myLoc, setMyLoc] = useState(null);
  const [radiusKm, setRadiusKm] = useState(50);
  const [pickupOnly, setPickupOnly] = useState(false);
  const [locBusy, setLocBusy] = useState(false);

  const detect = () => {
    if (!navigator.geolocation) return toast.error("Geolocation not supported");
    setLocBusy(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => { setMyLoc({ lat: pos.coords.latitude, lng: pos.coords.longitude }); setLocBusy(false); toast.success(`Showing pieces within ${radiusKm}km`); },
      (err) => { toast.error(err.code === 1 ? "Location permission denied" : "Couldn't get your location"); setLocBusy(false); }, { timeout: 8000 });
  };

  useEffect(() => { api.get("/upcycle/meta").then((r) => setMeta(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    setLoading(true);
    const p = new URLSearchParams({ section: "upcycle", sort, limit: 80 });
    if (type) p.set("furniture_type", type);
    if (pickupOnly) p.set("pickup_only", "true");
    if (myLoc) { p.set("near_lat", myLoc.lat); p.set("near_lng", myLoc.lng); p.set("radius_km", radiusKm); }
    api.get(`/artworks?${p}`).then((r) => setItems(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => setItems([])).finally(() => setLoading(false));
  }, [type, sort, pickupOnly, myLoc, radiusKm]);

  const chip = (active) => ({ borderColor: active ? "#CCFF00" : "rgba(255,255,255,0.1)", background: active ? "#CCFF0020" : "transparent", color: active ? "#CCFF00" : "#A1A1AA" });

  return (
    <div data-testid="upcycle-page" className="max-w-7xl mx-auto px-4 md:px-6 pt-8 md:pt-12 pb-32 overflow-x-hidden">
      <div className="grid lg:grid-cols-[1.2fr_1fr] gap-8 items-end mb-10">
        <div>
          <div className="label-caps text-[#34D399] flex items-center gap-2"><Recycle size={12} /> Furniture reborn as art</div>
          <h1 className="font-anton text-4xl sm:text-5xl lg:text-6xl uppercase mt-3 leading-[0.9]">Upcycle</h1>
          <p className="text-zinc-400 mt-4 text-sm md:text-base max-w-xl">Chairs, dressers, tables and lamps rescued from the curb and turned into one-of-a-kind painted pieces. Every listing is functional furniture and a finished artwork — flip any card to see what it looked like before.</p>
        </div>
        <div className="grid grid-cols-3 gap-2 md:gap-3 min-w-0">
          {[["Pieces", meta.total, Hammer], ["Types", meta.types.filter((t) => t.count).length, Recycle], ["Before/After", items.filter((a) => a.before_image).length, Sparkles]].map(([l, v, Icon]) => (
            <div key={l} className="border border-white/8 rounded-sm p-3 md:p-4 min-w-0"><Icon size={14} className="text-[#34D399]" /><div className="font-anton text-2xl md:text-3xl mt-2">{v}</div><div className="label-caps text-zinc-500 text-[9px] md:text-[10px] truncate">{l}</div></div>
          ))}
        </div>
      </div>

      <div className="flex gap-2 flex-wrap items-center mb-3">
        {myLoc ? (
          <button data-testid="upcycle-near-clear" onClick={() => setMyLoc(null)} className="label-caps text-xs px-3 py-1.5 rounded-full border flex items-center gap-1" style={chip(true)}><Navigation size={11} /> Near me · {radiusKm} km <X size={10} /></button>
        ) : (
          <button data-testid="upcycle-near-btn" onClick={detect} disabled={locBusy} className="label-caps text-xs px-3 py-1.5 rounded-full border flex items-center gap-1" style={chip(false)}><Navigation size={11} /> {locBusy ? "Locating…" : "Near me"}</button>
        )}
        {myLoc && <input data-testid="upcycle-radius" type="range" min="5" max="500" step="5" value={radiusKm} onChange={(e) => setRadiusKm(Number(e.target.value))} className="accent-[#CCFF00] w-32" />}
        <button data-testid="upcycle-pickup" onClick={() => setPickupOnly((v) => !v)} className="label-caps text-xs px-3 py-1.5 rounded-full border flex items-center gap-1" style={chip(pickupOnly)}><MapPin size={11} /> Local pickup only</button>
        <span className="text-[11px] text-zinc-500 flex items-center gap-1 ml-1"><Truck size={11} /> Sellers ship their own way or meet locally · Art Core takes just 4% + card processing · no listing fees</span>
      </div>
      <div className="flex gap-2 flex-wrap items-center mb-6 pb-4 border-b border-white/8">
        <button data-testid="upcycle-type-all" onClick={() => setType("")} className="label-caps text-xs px-3 py-1.5 rounded-full border" style={chip(!type)}>All</button>
        {meta.types.filter((t) => t.count > 0 || t.key === type).map((t) => (
          <button key={t.key} data-testid={`upcycle-type-${t.key}`} onClick={() => setType(type === t.key ? "" : t.key)} className="label-caps text-xs px-3 py-1.5 rounded-full border" style={chip(type === t.key)}>{t.label} <span className="opacity-60">{t.count}</span></button>
        ))}
        <select data-testid="upcycle-sort" value={sort} onChange={(e) => setSort(e.target.value)} className="ml-auto label-caps text-xs px-3 py-1.5 rounded-full border border-white/10 bg-[#0A0A0C] text-zinc-400 outline-none">
          <option value="recent">Newest</option><option value="price_asc">Price: Low</option><option value="price_desc">Price: High</option>
        </select>
        {(user?.role === "artist" || user?.role === "admin") && <Link to="/studio/upload?section=upcycle" data-testid="upcycle-list-btn" className="btn-lime !py-1.5 !px-3 text-xs flex items-center gap-1">List a piece <ArrowRight size={12} /></Link>}
      </div>

      {loading ? <div className="py-24 text-center label-caps text-zinc-500">Loading…</div> : items.length === 0 ? (
        <div className="border border-dashed border-white/10 rounded-sm p-16 text-center" data-testid="upcycle-empty"><Recycle size={28} className="mx-auto text-zinc-600 mb-3" /><div className="font-anton text-2xl uppercase">{myLoc ? "Nothing within range" : "Nothing here yet"}</div><div className="text-zinc-500 text-sm mt-2">{myLoc ? "Widen the radius or turn off Near me." : "Be the first to list an upcycled piece."}</div></div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 min-w-0" data-testid="upcycle-grid">
          {items.map((a) => (
            <div key={a.id} data-testid={`upcycle-card-${a.id}`} className="group min-w-0 border border-white/8 rounded-sm overflow-hidden bg-[#0F0F11] hover:border-white/20 transition-colors">
              <Link to={`/artwork/${a.id}`} className="block aspect-[3/4] relative overflow-hidden bg-white/[0.03]">
                <BeforeAfter before={a.before_image} after={a.images?.[0]} title={a.title} />
                <span className="absolute top-3 right-3 label-caps text-[10px] px-2 py-1 rounded-sm bg-[#34D399]/25 text-[#34D399] backdrop-blur-md">{meta.types.find((t) => t.key === a.furniture_type)?.label?.replace(/s$/, "") || "Upcycle"}</span>
                {a.status === "sold" && <span className="absolute bottom-3 right-3 label-caps text-[10px] px-2 py-1 rounded-sm bg-[#FF4D4D]/30 text-[#FF4D4D]">Sold</span>}
              </Link>
              <div className="p-4">
                <Link to={`/artwork/${a.id}`} className="font-unbounded font-semibold text-sm hover:text-[#CCFF00]">{a.title}</Link>
                <div className="text-xs text-zinc-500 mt-1 truncate">{a.materials || a.medium}</div>
                <div className="flex items-center gap-2 mt-2 text-[10px] label-caps">
                  {a.delivery?.includes("local_pickup") && <span className="px-1.5 py-0.5 rounded-sm bg-[#34D399]/15 text-[#34D399] flex items-center gap-1"><MapPin size={9} /> Pickup{a.location?.city ? ` · ${a.location.city}` : ""}</span>}
                  {a.delivery?.includes("ships") && <span className="px-1.5 py-0.5 rounded-sm bg-white/5 text-zinc-400 flex items-center gap-1"><Truck size={9} /> Ships</span>}
                  {a.distance_km != null && <span className="text-[#CCFF00]">{a.distance_km} km away</span>}
                </div>
                <div className="flex items-center justify-between mt-3"><Link to={`/artist/${a.artist_id}`} className="text-xs text-zinc-400 hover:text-white">{a.artist?.name || "Artist"}</Link><span className="font-anton text-xl text-[#CCFF00]">${Number(a.price).toLocaleString()}</span></div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
