import React, { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin, Calendar, Users, Plus, List as ListIcon, Map as MapIcon, X, Search, Navigation, Bookmark, Share2, Ticket, Flame } from "lucide-react";
import { toast } from "sonner";
import { api, fileUrl } from "../api";
import { useAuth } from "../context/AuthContext";
import { CreateEventModal } from "../components/events/CreateEventModal";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

export const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));
const FALLBACK_CAT = { key: "exhibition", label: "Event", color: "#A1A1AA" };

const startOf = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
const DATE_PRESETS = [
  ["today", "Today", () => { const s = startOf(new Date()); const e = new Date(s); e.setDate(e.getDate() + 1); return [s, e]; }],
  ["weekend", "This weekend", () => { const s = startOf(new Date()); const day = s.getDay(); const sat = new Date(s); sat.setDate(s.getDate() + ((6 - day + 7) % 7)); const mon = new Date(sat); mon.setDate(sat.getDate() + 2); return [day === 0 ? s : sat, mon]; }],
  ["week", "Next 7 days", () => { const s = new Date(); const e = new Date(s); e.setDate(e.getDate() + 7); return [s, e]; }],
  ["month", "This month", () => { const s = new Date(); const e = new Date(s.getFullYear(), s.getMonth() + 1, 1); return [s, e]; }],
];

function niceDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
function dayKey(iso) { return new Date(iso).toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" }); }

export function shareEvent(ev) {
  const url = `${process.env.REACT_APP_BACKEND_URL}/api/share/event/${ev.id}`;
  if (navigator.share) navigator.share({ title: ev.title, url }).catch(() => {});
  else { navigator.clipboard?.writeText(url); toast.success("Link copied"); }
}

export async function toggleSaveEvent(ev, user, onChange) {
  if (!user) return toast.error("Log in to save events");
  try {
    const r = await api.post(`/events/${ev.id}/save`);
    toast.success(r.data.saved ? "Saved — we'll remind you" : "Removed from saved");
    onChange?.();
  } catch { toast.error("Failed"); }
}

export default function Events() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [events, setEvents] = useState([]);
  const [cats, setCats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("list");
  const [showCreate, setShowCreate] = useState(false);
  const [myLocation, setMyLocation] = useState(null);
  const [radiusKm, setRadiusKm] = useState(50);
  const [locBusy, setLocBusy] = useState(false);
  const [q, setQ] = useState(params.get("q") || "");
  const [qInput, setQInput] = useState(params.get("q") || "");
  const [category, setCategory] = useState(params.get("category") || "");
  const [datePreset, setDatePreset] = useState("");
  const [customRange, setCustomRange] = useState({ from: "", to: "" });
  const [sort, setSort] = useState("soonest");
  const [savedOnly, setSavedOnly] = useState(false);
  const [freeOnly, setFreeOnly] = useState(false);

  useEffect(() => { api.get("/events/meta/categories").then((r) => setCats(r.data)).catch(() => {}); }, []);
  const catMeta = (k) => cats.find((c) => c.key === k) || FALLBACK_CAT;

  const range = useMemo(() => {
    if (customRange.from || customRange.to) return [customRange.from ? new Date(customRange.from) : null, customRange.to ? new Date(customRange.to + "T23:59:59") : null];
    const p = DATE_PRESETS.find((x) => x[0] === datePreset);
    return p ? p[2]() : [null, null];
  }, [datePreset, customRange]);

  const load = () => {
    setLoading(true);
    const p = new URLSearchParams();
    if (category) p.set("category", category);
    if (q) p.set("q", q);
    if (range[0]) p.set("date_from", range[0].toISOString());
    if (range[1]) p.set("date_to", range[1].toISOString());
    if (sort !== "soonest") p.set("sort", sort);
    if (savedOnly && user) p.set("saved_only", "true");
    if (freeOnly) p.set("free_only", "true");
    if (myLocation) { p.set("near_lat", myLocation.lat); p.set("near_lng", myLocation.lng); p.set("radius_km", radiusKm); }
    api.get(`/events?${p}`).then((r) => setEvents(r.data)).catch(() => setEvents([])).finally(() => setLoading(false));
    const sp = {}; if (q) sp.q = q; if (category) sp.category = category; setParams(sp, { replace: true });
  };
  useEffect(() => { load(); }, [category, q, range, sort, savedOnly, freeOnly, myLocation, radiusKm]); // eslint-disable-line

  const detectLocation = () => {
    if (!navigator.geolocation) return toast.error("Geolocation not supported");
    setLocBusy(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => { setMyLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }); setSort("distance"); setLocBusy(false); toast.success(`Events within ${radiusKm}km`); },
      (err) => { toast.error(err.code === 1 ? "Location permission denied" : "Couldn't get your location"); setLocBusy(false); },
      { timeout: 8000, maximumAge: 300000 },
    );
  };

  const canHost = user?.role === "artist" || user?.role === "admin";
  const chip = (active, color = "#CCFF00") => ({ borderColor: active ? color : "rgba(255,255,255,0.1)", background: active ? `${color}20` : "transparent", color: active ? color : "#A1A1AA" });
  const activeFilters = [category, q, datePreset, customRange.from, customRange.to, savedOnly, freeOnly, myLocation].filter(Boolean).length;
  const reset = () => { setCategory(""); setQ(""); setQInput(""); setDatePreset(""); setCustomRange({ from: "", to: "" }); setSavedOnly(false); setFreeOnly(false); setMyLocation(null); setSort("soonest"); };

  return (
    <div data-testid="events-page" className="max-w-7xl mx-auto px-4 md:px-6 pt-8 md:pt-12 pb-32">
      <div className="grid lg:grid-cols-[1fr_auto] gap-6 items-end mb-8">
        <div>
          <div className="label-caps text-[#FF4D4D]"><MapPin size={12} className="inline mr-2" /> Local art discovery</div>
          <h1 className="font-anton text-4xl sm:text-5xl lg:text-6xl uppercase mt-3 leading-[0.9]">What's on<br />near you</h1>
          <p className="text-zinc-500 mt-3 text-sm md:text-base max-w-xl">Exhibitions, openings, festivals, street art, classes, auctions and pop-ups — hosted by real artists and organizers on Art Core.</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button data-testid="view-list" onClick={() => setView("list")} className={`btn-ghost !py-2 !px-3 flex items-center gap-1 ${view === "list" ? "!border-[#CCFF00] !text-[#CCFF00]" : ""}`}><ListIcon size={14} /> List</button>
          <button data-testid="view-map" onClick={() => setView("map")} className={`btn-ghost !py-2 !px-3 flex items-center gap-1 ${view === "map" ? "!border-[#CCFF00] !text-[#CCFF00]" : ""}`}><MapIcon size={14} /> Map</button>
          {canHost && <button data-testid="create-event-btn" onClick={() => setShowCreate(true)} className="btn-lime !py-2 !px-3 flex items-center gap-1"><Plus size={14} /> Host</button>}
        </div>
      </div>

      {/* Search + location */}
      <form onSubmit={(e) => { e.preventDefault(); setQ(qInput.trim()); }} className="flex flex-col md:flex-row gap-2 mb-4">
        <div className="flex-1 flex items-center gap-2 bg-white/[0.03] border border-white/12 rounded-sm px-3 focus-within:border-[#CCFF00]">
          <Search size={14} className="text-zinc-500 flex-shrink-0" />
          <input data-testid="events-search" value={qInput} onChange={(e) => setQInput(e.target.value)} placeholder="Search events, venues, cities, artists…"
            className="w-full bg-transparent py-3 text-sm outline-none" />
          {qInput && <button type="button" onClick={() => { setQInput(""); setQ(""); }} className="text-zinc-500"><X size={14} /></button>}
        </div>
        <button data-testid="events-search-btn" type="submit" className="btn-ghost !py-3 !px-4 text-xs">Search</button>
        {myLocation ? (
          <button type="button" data-testid="near-me-clear" onClick={() => { setMyLocation(null); setSort("soonest"); }}
            className="btn-ghost !py-3 !px-4 text-xs flex items-center gap-2 !border-[#CCFF00] !text-[#CCFF00]"><Navigation size={12} /> Near me · {radiusKm}km <X size={11} /></button>
        ) : (
          <button type="button" data-testid="near-me-btn" onClick={detectLocation} disabled={locBusy} className="btn-ghost !py-3 !px-4 text-xs flex items-center gap-2"><Navigation size={12} /> {locBusy ? "Locating…" : "Near me"}</button>
        )}
      </form>
      {myLocation && (
        <div className="flex items-center gap-3 text-xs text-zinc-500 mb-4">
          <span>Radius</span>
          <input data-testid="radius-slider" type="range" min="5" max="500" step="5" value={radiusKm} onChange={(e) => setRadiusKm(Number(e.target.value))} className="accent-[#CCFF00] flex-1 max-w-xs" />
          <span className="text-white font-anton min-w-[4ch]">{radiusKm} km</span>
        </div>
      )}

      {/* Date + category chips */}
      <div className="flex gap-2 flex-wrap items-center mb-3">
        <Calendar size={12} className="text-zinc-500" />
        <button data-testid="date-any" onClick={() => { setDatePreset(""); setCustomRange({ from: "", to: "" }); }} className="label-caps text-xs px-3 py-1.5 rounded-full border" style={chip(!datePreset && !customRange.from && !customRange.to)}>Any date</button>
        {DATE_PRESETS.map(([k, l]) => (
          <button key={k} data-testid={`date-${k}`} onClick={() => { setDatePreset(k); setCustomRange({ from: "", to: "" }); }} className="label-caps text-xs px-3 py-1.5 rounded-full border" style={chip(datePreset === k)}>{l}</button>
        ))}
        <div className="flex items-center gap-1 text-xs text-zinc-500">
          <input data-testid="date-from" type="date" value={customRange.from} onChange={(e) => { setDatePreset(""); setCustomRange((r) => ({ ...r, from: e.target.value })); }} className="bg-white/[0.03] border border-white/12 rounded-full px-2 py-1 text-xs outline-none" />
          <span>→</span>
          <input data-testid="date-to" type="date" value={customRange.to} onChange={(e) => { setDatePreset(""); setCustomRange((r) => ({ ...r, to: e.target.value })); }} className="bg-white/[0.03] border border-white/12 rounded-full px-2 py-1 text-xs outline-none" />
        </div>
      </div>
      <div className="flex gap-2 flex-wrap items-center mb-3">
        <button data-testid="filter-cat-all" onClick={() => setCategory("")} className="label-caps text-xs px-3 py-1.5 rounded-full border" style={chip(!category)}>All</button>
        {cats.map((c) => (
          <button key={c.key} data-testid={`filter-cat-${c.key}`} onClick={() => setCategory(category === c.key ? "" : c.key)} className="label-caps text-xs px-3 py-1.5 rounded-full border" style={chip(category === c.key, c.color)}>{c.label}</button>
        ))}
      </div>
      <div className="flex gap-2 flex-wrap items-center mb-6 pb-4 border-b border-white/8">
        {user && <button data-testid="filter-saved" onClick={() => setSavedOnly((v) => !v)} className="label-caps text-xs px-3 py-1.5 rounded-full border flex items-center gap-1" style={chip(savedOnly, "#FF6EC7")}><Bookmark size={11} /> Saved</button>}
        <button data-testid="filter-free" onClick={() => setFreeOnly((v) => !v)} className="label-caps text-xs px-3 py-1.5 rounded-full border" style={chip(freeOnly, "#34D399")}>Free</button>
        <select data-testid="events-sort" value={sort} onChange={(e) => setSort(e.target.value)} className="label-caps text-xs px-3 py-1.5 rounded-full border border-white/10 bg-[#0A0A0C] text-zinc-400 outline-none">
          <option value="soonest">Soonest first</option>
          <option value="trending">Trending</option>
          {myLocation && <option value="distance">Closest first</option>}
        </select>
        <span className="text-xs text-zinc-500 ml-auto" data-testid="events-count">{loading ? "Loading…" : `${events.length} event${events.length === 1 ? "" : "s"}`}</span>
        {activeFilters > 0 && <button data-testid="events-reset" onClick={reset} className="label-caps text-xs text-[#FF4D4D]">Reset</button>}
      </div>

      {view === "map" ? (
        <EventsMap events={events} myLocation={myLocation} radiusKm={radiusKm} catMeta={catMeta} user={user} onChange={load} />
      ) : (
        <EventsList events={events} loading={loading} catMeta={catMeta} user={user} onChange={load} savedOnly={savedOnly} />
      )}

      {showCreate && <CreateEventModal categories={cats} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} />}
    </div>
  );
}

function EventsList({ events, loading, catMeta, user, onChange, savedOnly }) {
  if (loading && events.length === 0) return <div className="py-24 text-center label-caps text-zinc-500">Loading events…</div>;
  if (events.length === 0) return (
    <div className="border border-dashed border-white/10 rounded-sm p-16 text-center" data-testid="events-empty">
      <Calendar size={28} className="mx-auto text-zinc-600 mb-3" />
      <div className="font-anton text-2xl uppercase">{savedOnly ? "No saved events yet" : "Nothing matches"}</div>
      <div className="text-zinc-500 text-sm mt-2">{savedOnly ? "Tap the bookmark on any event to save it here." : "Try another date, category, or widen your radius."}</div>
    </div>
  );
  const groups = events.reduce((acc, e) => { const k = dayKey(e.start_at); (acc[k] = acc[k] || []).push(e); return acc; }, {});
  return (
    <div className="space-y-10" data-testid="events-list-view">
      {Object.entries(groups).map(([day, list]) => (
        <section key={day}>
          <div className="flex items-center gap-3 mb-4"><div className="font-anton text-xl uppercase">{day}</div><div className="flex-1 h-px bg-white/8" /></div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {list.map((e) => <EventCard key={e.id} event={e} catMeta={catMeta} user={user} onChange={onChange} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

export function EventCard({ event, catMeta, user, onChange }) {
  const meta = catMeta(event.category);
  const full = event.max_capacity && event.rsvp_count >= event.max_capacity;
  const trending = event.rsvp_count >= 5;
  return (
    <div data-testid={`event-card-${event.id}`} className="group border border-white/8 rounded-sm overflow-hidden bg-[#0F0F11] hover:border-white/20 transition-colors flex flex-col">
      <Link to={`/events/${event.id}`} className="relative block aspect-[16/10] overflow-hidden bg-white/[0.03]">
        {event.cover_image ? <img src={resolveImg(event.cover_image)} alt="" loading="lazy" className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500" />
          : <div className="w-full h-full flex items-center justify-center text-zinc-700"><Calendar size={28} /></div>}
        <div className="absolute top-2 left-2 flex gap-1.5">
          <span className="label-caps text-[10px] px-2 py-1 rounded-sm backdrop-blur-md" style={{ background: `${meta.color}33`, color: meta.color }}>{meta.label}</span>
          {trending && <span className="label-caps text-[10px] px-2 py-1 rounded-sm bg-[#FF4D4D]/30 text-[#FF4D4D] backdrop-blur-md flex items-center gap-1"><Flame size={10} /> Hot</span>}
        </div>
        <div className="absolute bottom-2 left-2 label-caps text-[10px] px-2 py-1 rounded-sm bg-black/60 backdrop-blur-md text-white">
          {event.is_free ? "Free" : `$${Number(event.ticket_price).toLocaleString()}`}{event.distance_km != null ? ` · ${event.distance_km} km` : ""}
        </div>
      </Link>
      <div className="p-4 flex-1 flex flex-col">
        <div className="text-xs text-[#CCFF00] label-caps">{niceDate(event.start_at)}</div>
        <Link to={`/events/${event.id}`} className="font-unbounded font-semibold text-sm mt-1.5 leading-snug line-clamp-2 hover:text-[#CCFF00]">{event.title}</Link>
        <div className="text-xs text-zinc-500 mt-2 flex items-center gap-1 truncate"><MapPin size={11} className="flex-shrink-0" /> {[event.venue, event.location?.city || event.location?.address].filter(Boolean).join(" · ") || "Location TBA"}</div>
        <div className="text-xs text-zinc-500 mt-1 truncate">by {event.organizer || event.host_name}</div>
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/8">
          <span className="text-xs text-zinc-400 flex items-center gap-1"><Users size={12} /> {event.rsvp_count}{event.max_capacity ? `/${event.max_capacity}` : ""}{full ? " · Full" : ""}</span>
          <div className="flex items-center gap-1">
            <button data-testid={`save-event-${event.id}`} onClick={() => toggleSaveEvent(event, user, onChange)} title="Save"
              className={`p-1.5 rounded-sm hover:bg-white/5 ${event.saved ? "text-[#FF6EC7]" : "text-zinc-500"}`}><Bookmark size={14} fill={event.saved ? "currentColor" : "none"} /></button>
            <button data-testid={`share-event-${event.id}`} onClick={() => shareEvent(event)} title="Share" className="p-1.5 rounded-sm hover:bg-white/5 text-zinc-500"><Share2 size={14} /></button>
            <Link to={`/events/${event.id}`} data-testid={`rsvp-link-${event.id}`} className="ml-1 label-caps text-[10px] px-2.5 py-1.5 rounded-sm border border-[#CCFF00]/40 text-[#CCFF00] hover:bg-[#CCFF00]/10 flex items-center gap-1">
              <Ticket size={11} /> {event.rsvped ? "Going" : event.is_free ? "RSVP" : "Tickets"}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function EventsMap({ events, myLocation, radiusKm, catMeta, user, onChange }) {
  const [selected, setSelected] = useState(null);
  const center = useMemo(() => {
    if (myLocation) return [myLocation.lat, myLocation.lng];
    if (events.length === 0) return [40.7128, -74.006];
    return [events.reduce((s, e) => s + e.location.lat, 0) / events.length, events.reduce((s, e) => s + e.location.lng, 0) / events.length];
  }, [events, myLocation]);
  const meIcon = useMemo(() => L.divIcon({ className: "", html: '<div style="width:16px;height:16px;background:#CCFF00;border:2px solid #0A0A0C;border-radius:50%;box-shadow:0 0 0 6px rgba(204,255,0,0.25)"></div>', iconSize: [16, 16], iconAnchor: [8, 8] }), []);
  const pin = (color, active) => L.divIcon({ className: "", iconSize: [26, 26], iconAnchor: [13, 26], popupAnchor: [0, -26],
    html: `<div style="width:26px;height:26px;background:${color};border:2px solid #0A0A0C;border-radius:50% 50% 50% 0;transform:rotate(-45deg) scale(${active ? 1.25 : 1});box-shadow:0 2px 8px rgba(0,0,0,.6)"></div>` });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-4 h-[60vh] md:h-[70vh]" data-testid="events-map-view">
      <div className="border border-white/8 rounded-sm overflow-hidden h-full min-h-[300px]">
        <MapContainer center={center} zoom={4} scrollWheelZoom style={{ height: "100%", width: "100%", background: "#0A0A0C" }}>
          <TileLayer attribution='&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" className="grayscale contrast-125" />
          <FitToBounds events={events} myLocation={myLocation} radiusKm={radiusKm} />
          {myLocation && (<>
            <Marker position={[myLocation.lat, myLocation.lng]} icon={meIcon}><Popup>You are here</Popup></Marker>
            <Circle center={[myLocation.lat, myLocation.lng]} radius={radiusKm * 1000} pathOptions={{ color: "#CCFF00", fillColor: "#CCFF00", fillOpacity: 0.05, weight: 1, dashArray: "6 6" }} />
          </>)}
          {events.map((e) => (
            <Marker key={e.id} position={[e.location.lat, e.location.lng]} icon={pin(catMeta(e.category).color, selected?.id === e.id)} eventHandlers={{ click: () => setSelected(e) }}>
              <Popup>
                <div style={{ minWidth: 200 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{e.title}</div>
                  <div style={{ fontSize: 11, color: "#666" }}>{niceDate(e.start_at)}</div>
                  <div style={{ fontSize: 12, marginTop: 4 }}>{[e.venue, e.location.city].filter(Boolean).join(" · ")}</div>
                  <Link to={`/events/${e.id}`} style={{ color: "#7C3AED", fontSize: 12, display: "inline-block", marginTop: 6 }}>View →</Link>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
      <div className="border border-white/8 rounded-sm overflow-y-auto max-h-[70vh]" data-testid="events-side-list">
        {events.length === 0 ? <div className="text-center py-16 label-caps text-zinc-500 px-4">No events {myLocation ? "in range" : "match"}.</div> : (
          <div className="divide-y divide-white/8">
            {events.map((e) => {
              const m = catMeta(e.category);
              return (
                <Link key={e.id} to={`/events/${e.id}`} data-testid={`event-mini-${e.id}`} onMouseEnter={() => setSelected(e)} className={`block p-4 hover:bg-white/[0.04] ${selected?.id === e.id ? "bg-white/[0.04]" : ""}`}>
                  <div className="flex items-start gap-3">
                    {e.cover_image && <img src={resolveImg(e.cover_image)} alt="" className="w-16 h-16 object-cover rounded-sm flex-shrink-0" loading="lazy" />}
                    <div className="flex-1 min-w-0">
                      <div className="label-caps text-[10px]" style={{ color: m.color }}>{m.label}{e.distance_km != null ? ` · ${e.distance_km} km` : ""}</div>
                      <div className="font-unbounded text-xs font-semibold mt-1 truncate">{e.title}</div>
                      <div className="text-[11px] text-zinc-500 mt-1">{niceDate(e.start_at)}</div>
                      <div className="text-[11px] text-zinc-500 truncate">{[e.venue, e.location.city].filter(Boolean).join(" · ")}</div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function FitToBounds({ events, myLocation, radiusKm }) {
  const map = useMap();
  useEffect(() => {
    const points = events.map((e) => [e.location.lat, e.location.lng]);
    if (myLocation) points.push([myLocation.lat, myLocation.lng]);
    if (points.length === 0) return;
    if (points.length === 1) { map.setView(points[0], myLocation ? 10 : 12); return; }
    map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 12 });
  }, [events, myLocation, radiusKm, map]);
  return null;
}
