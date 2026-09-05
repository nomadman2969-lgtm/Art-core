import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin, Calendar, Users, Plus, List as ListIcon, Map as MapIcon, X, Loader2, Search, Navigation } from "lucide-react";
import { toast } from "sonner";
import { api, fileUrl } from "../api";
import { useAuth } from "../context/AuthContext";

// Fix leaflet default icon on webpack (icons can't resolve their default paths)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const CATEGORIES = [
  { key: "gallery_opening", label: "Gallery Opening", color: "#D4AF37" },
  { key: "pop_up", label: "Pop-up", color: "#FF4D4D" },
  { key: "festival", label: "Festival", color: "#FF6EC7" },
  { key: "meetup", label: "Meetup", color: "#7C3AED" },
  { key: "workshop", label: "Workshop", color: "#00E5FF" },
  { key: "live_painting", label: "Live Painting", color: "#F5A623" },
  { key: "virtual", label: "Virtual", color: "#CCFF00" },
  { key: "market", label: "Art Market", color: "#00E5FF" },
];

const catMeta = (k) => CATEGORIES.find((c) => c.key === k) || CATEGORIES[0];
const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

function niceDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function Events() {
  const { user } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("map"); // map | list
  const [category, setCategory] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [myLocation, setMyLocation] = useState(null); // {lat, lng} or null
  const [radiusKm, setRadiusKm] = useState(50);
  const [locBusy, setLocBusy] = useState(false);

  const load = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (myLocation) {
      params.set("near_lat", String(myLocation.lat));
      params.set("near_lng", String(myLocation.lng));
      params.set("radius_km", String(radiusKm));
    }
    const q = params.toString();
    api.get(`/events${q ? `?${q}` : ""}`).then((r) => setEvents(r.data)).catch(() => setEvents([])).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [category, myLocation, radiusKm]);

  const detectLocation = () => {
    if (!navigator.geolocation) { toast.error("Geolocation not supported"); return; }
    setLocBusy(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setMyLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        toast.success(`Showing events within ${radiusKm}km`);
        setLocBusy(false);
      },
      (err) => {
        toast.error(err.code === 1 ? "Location permission denied" : "Couldn't get your location");
        setLocBusy(false);
      },
      { timeout: 8000, maximumAge: 5 * 60 * 1000 }
    );
  };
  const clearLocation = () => { setMyLocation(null); toast("Showing events worldwide"); };

  const canHost = user?.role === "artist" || user?.role === "admin";

  return (
    <div data-testid="events-page" className="max-w-6xl mx-auto px-4 md:px-6 pt-10 pb-32">
      <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
        <div>
          <div className="label-caps text-[#FF4D4D]"><MapPin size={12} className="inline mr-2" /> On the Map</div>
          <h1 className="font-anton text-5xl md:text-6xl uppercase mt-3">Events</h1>
          <div className="text-zinc-500 mt-2">Openings, pop-ups, festivals — meet artists in person.</div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button data-testid="view-map" onClick={() => setView("map")}
            className={`btn-ghost !py-2 !px-3 flex items-center gap-1 ${view === "map" ? "!border-[#CCFF00] !text-[#CCFF00]" : ""}`}>
            <MapIcon size={14} /> Map
          </button>
          <button data-testid="view-list" onClick={() => setView("list")}
            className={`btn-ghost !py-2 !px-3 flex items-center gap-1 ${view === "list" ? "!border-[#CCFF00] !text-[#CCFF00]" : ""}`}>
            <ListIcon size={14} /> List
          </button>
          {canHost && (
            <button data-testid="create-event-btn" onClick={() => setShowCreate(true)} className="btn-lime !py-2 !px-3 flex items-center gap-1">
              <Plus size={14} /> Host
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap mb-4 items-center">
        <button data-testid="filter-cat-all" onClick={() => setCategory("")}
          className="label-caps text-xs px-3 py-1.5 rounded-full border transition-colors"
          style={{ borderColor: !category ? "#CCFF00" : "rgba(255,255,255,0.1)", background: !category ? "#CCFF0020" : "transparent", color: !category ? "#CCFF00" : "#A1A1AA" }}>All</button>
        {CATEGORIES.map((c) => (
          <button key={c.key} data-testid={`filter-cat-${c.key}`} onClick={() => setCategory(c.key)}
            className="label-caps text-xs px-3 py-1.5 rounded-full border transition-colors"
            style={{ borderColor: category === c.key ? c.color : "rgba(255,255,255,0.1)", background: category === c.key ? `${c.color}20` : "transparent", color: category === c.key ? c.color : "#A1A1AA" }}>
            {c.label}
          </button>
        ))}
      </div>

      {/* Near me controls */}
      <div className="flex gap-2 items-center flex-wrap mb-6 pb-4 border-b border-white/8">
        {myLocation ? (
          <>
            <button data-testid="near-me-clear" onClick={clearLocation}
              className="label-caps text-xs px-3 py-1.5 rounded-full border border-[#CCFF00] bg-[#CCFF00]/15 text-[#CCFF00] flex items-center gap-1.5">
              <Navigation size={12} /> Near me · {radiusKm}km <X size={11} className="ml-1" />
            </button>
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span>Radius</span>
              <input data-testid="radius-slider" type="range" min="5" max="500" step="5" value={radiusKm}
                onChange={(e) => setRadiusKm(Number(e.target.value))} className="accent-[#CCFF00]" />
              <span className="text-white font-anton min-w-[3ch] text-right">{radiusKm}</span>
              <span>km</span>
            </div>
          </>
        ) : (
          <button data-testid="near-me-btn" onClick={detectLocation} disabled={locBusy}
            className="label-caps text-xs px-3 py-1.5 rounded-full border border-white/12 text-zinc-300 hover:border-[#CCFF00] hover:text-[#CCFF00] flex items-center gap-1.5">
            {locBusy ? <Loader2 size={12} className="animate-spin" /> : <Navigation size={12} />} Near me
          </button>
        )}
        <div className="text-xs text-zinc-500 ml-auto">
          {events.length} {events.length === 1 ? "event" : "events"} {myLocation ? `within ${radiusKm}km` : "worldwide"}
        </div>
      </div>

      {loading && !events.length ? (
        <div className="text-center py-16 label-caps text-zinc-500">Loading...</div>
      ) : (
        <>
          {view === "map" && <EventsMap events={events} myLocation={myLocation} radiusKm={radiusKm} onChange={load} />}
          {view === "list" && <EventsList events={events} onChange={load} />}
        </>
      )}

      {showCreate && (
        <CreateEventModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} />
      )}
    </div>
  );
}

function EventsMap({ events, myLocation, radiusKm, onChange }) {
  const [selected, setSelected] = useState(null);
  // Default center — user location if available, else auto-fit events, else NYC-ish
  const center = useMemo(() => {
    if (myLocation) return [myLocation.lat, myLocation.lng];
    if (events.length === 0) return [40.7128, -74.006];
    const avgLat = events.reduce((s, e) => s + e.location.lat, 0) / events.length;
    const avgLng = events.reduce((s, e) => s + e.location.lng, 0) / events.length;
    return [avgLat, avgLng];
  }, [events, myLocation]);

  // Custom icon for the "you are here" marker (lime dot)
  const meIcon = useMemo(() => L.divIcon({
    className: "",
    html: '<div style="width:16px;height:16px;background:#CCFF00;border:2px solid #0A0A0C;border-radius:50%;box-shadow:0 0 0 6px rgba(204,255,0,0.25)"></div>',
    iconSize: [16, 16], iconAnchor: [8, 8],
  }), []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 h-[70vh]" data-testid="events-map-view">
      <div className="border border-white/8 rounded-sm overflow-hidden h-full">
        <MapContainer center={center} zoom={events.length || myLocation ? 4 : 3} scrollWheelZoom style={{ height: "100%", width: "100%", background: "#0A0A0C" }}>
          <TileLayer
            attribution='&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            className="grayscale contrast-125"
          />
          <FitToBounds events={events} myLocation={myLocation} radiusKm={radiusKm} />
          {myLocation && (
            <>
              <Marker position={[myLocation.lat, myLocation.lng]} icon={meIcon}>
                <Popup>You are here</Popup>
              </Marker>
              <Circle center={[myLocation.lat, myLocation.lng]} radius={radiusKm * 1000}
                pathOptions={{ color: "#CCFF00", fillColor: "#CCFF00", fillOpacity: 0.05, weight: 1, dashArray: "6 6" }} />
            </>
          )}
          {events.map((e) => (
            <Marker key={e.id} position={[e.location.lat, e.location.lng]} eventHandlers={{ click: () => setSelected(e) }}>
              <Popup>
                <div style={{ minWidth: 200 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{e.title}</div>
                  <div style={{ fontSize: 11, color: "#666" }}>{niceDate(e.start_at)}</div>
                  <div style={{ fontSize: 12, marginTop: 4 }}>{e.location.city || e.location.address || ""}</div>
                  <Link to={`/events/${e.id}`} style={{ color: "#7C3AED", fontSize: 12, display: "inline-block", marginTop: 6 }}>View →</Link>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
      <div className="border border-white/8 rounded-sm overflow-y-auto max-h-[70vh]" data-testid="events-side-list">
        {events.length === 0 ? (
          <div className="text-center py-16 label-caps text-zinc-500 px-4">No events {myLocation ? "in range" : "yet"}.</div>
        ) : (
          <div className="divide-y divide-white/8">
            {events.map((e) => (
              <MiniEventCard key={e.id} event={e} onSelect={() => setSelected(e)} active={selected?.id === e.id} onChange={onChange} />
            ))}
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
    if (points.length === 1) {
      map.setView(points[0], myLocation ? 10 : 12);
      return;
    }
    const bounds = L.latLngBounds(points);
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
  }, [events, myLocation, radiusKm, map]);
  return null;
}

function MiniEventCard({ event, onSelect, active, onChange }) {
  const meta = catMeta(event.category);
  return (
    <Link
      to={`/events/${event.id}`}
      data-testid={`event-mini-${event.id}`}
      onMouseEnter={onSelect}
      className={`block p-4 hover:bg-white/[0.04] ${active ? "bg-white/[0.04]" : ""}`}>
      <div className="flex items-start gap-3">
        {event.cover_image && (
          <img src={resolveImg(event.cover_image)} alt="" className="w-16 h-16 object-cover rounded-sm flex-shrink-0" loading="lazy" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="label-caps text-[10px] px-1.5 py-0.5 rounded-sm" style={{ background: `${meta.color}22`, color: meta.color }}>{meta.label}</span>
            {event.is_free ? <span className="label-caps text-[10px] text-[#CCFF00]">Free</span> : <span className="label-caps text-[10px] text-[#F5A623]">${event.ticket_price}</span>}
          </div>
          <div className="font-unbounded font-semibold text-sm truncate">{event.title}</div>
          <div className="text-xs text-zinc-500 mt-1 flex items-center gap-1"><Calendar size={10} /> {niceDate(event.start_at)}</div>
          <div className="text-xs text-zinc-500 flex items-center gap-1"><MapPin size={10} /> {event.location.city || event.location.address || "TBA"}</div>
          <div className="text-xs text-zinc-500 flex items-center gap-1 mt-1"><Users size={10} /> {event.rsvp_count} RSVPs</div>
        </div>
      </div>
    </Link>
  );
}

function EventsList({ events, onChange }) {
  if (events.length === 0) return (
    <div className="border border-dashed border-white/10 py-24 text-center rounded-sm">
      <div className="label-caps text-zinc-500">No events match yet.</div>
    </div>
  );
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="events-list-view">
      {events.map((e) => (
        <EventCard key={e.id} event={e} onChange={onChange} />
      ))}
    </div>
  );
}

function EventCard({ event, onChange }) {
  const meta = catMeta(event.category);
  return (
    <Link to={`/events/${event.id}`} data-testid={`event-card-${event.id}`}
      className="border border-white/8 rounded-sm overflow-hidden hover:border-[#CCFF00]/40 transition-colors bg-[#121214] flex flex-col">
      {event.cover_image ? (
        <img src={resolveImg(event.cover_image)} alt={event.title} className="w-full h-40 object-cover" loading="lazy" />
      ) : (
        <div className="w-full h-40 flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${meta.color}30, #0A0A0C)` }}>
          <MapPin size={32} className="text-white/40" />
        </div>
      )}
      <div className="p-4 flex-1 flex flex-col">
        <div className="flex items-center gap-2 mb-2">
          <span className="label-caps text-[10px] px-1.5 py-0.5 rounded-sm" style={{ background: `${meta.color}22`, color: meta.color }}>{meta.label}</span>
          {event.is_free ? <span className="label-caps text-[10px] text-[#CCFF00]">Free</span> : <span className="label-caps text-[10px] text-[#F5A623]">${event.ticket_price}</span>}
        </div>
        <div className="font-anton text-xl uppercase leading-tight">{event.title}</div>
        <div className="text-xs text-zinc-400 mt-2 flex items-center gap-1"><Calendar size={10} /> {niceDate(event.start_at)}</div>
        <div className="text-xs text-zinc-500 flex items-center gap-1 truncate"><MapPin size={10} /> {event.location.city || event.location.address || "TBA"}</div>
        <div className="text-xs text-zinc-500 flex items-center gap-1 mt-1"><Users size={10} /> {event.rsvp_count} RSVPs</div>
      </div>
    </Link>
  );
}

/* ---------------- Create Event Modal ---------------- */
function CreateEventModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    title: "", description: "", category: "gallery_opening",
    address: "", city: "", lat: "", lng: "",
    start_at: "", end_at: "",
    is_free: true, ticket_price: "",
    cover_image: null,
  });
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [geocoding, setGeocoding] = useState(false);

  const setF = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", file);
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setF("cover_image", r.data.path);
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };

  const geocode = async () => {
    const query = [form.address, form.city].filter(Boolean).join(", ");
    if (!query.trim()) { toast.error("Enter an address or city first"); return; }
    setGeocoding(true);
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`,
        { headers: { "Accept": "application/json" } });
      const data = await r.json();
      if (data && data[0]) {
        setF("lat", parseFloat(data[0].lat).toFixed(6));
        setF("lng", parseFloat(data[0].lon).toFixed(6));
        toast.success("Location found");
      } else {
        toast.error("Couldn't find that place");
      }
    } catch { toast.error("Geocoding failed"); }
    setGeocoding(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.title || !form.description || !form.start_at || !form.lat || !form.lng) {
      toast.error("Fill title, description, start time, and location");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        title: form.title,
        description: form.description,
        category: form.category,
        location: {
          lat: parseFloat(form.lat), lng: parseFloat(form.lng),
          address: form.address || null, city: form.city || null,
        },
        start_at: new Date(form.start_at).toISOString(),
        end_at: form.end_at ? new Date(form.end_at).toISOString() : null,
        cover_image: form.cover_image,
        is_free: form.is_free,
        ticket_price: form.is_free ? null : parseFloat(form.ticket_price) || 0,
      };
      await api.post("/events", payload);
      toast.success("Event created");
      onCreated();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
    setSaving(false);
  };

  return (
    <div data-testid="create-event-modal" onClick={onClose}
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-3 md:p-6 overflow-y-auto">
      <div onClick={(e) => e.stopPropagation()} className="bg-[#121214] border border-white/10 rounded-sm w-full max-w-2xl my-auto">
        <div className="flex items-center justify-between p-4 border-b border-white/8">
          <div className="font-unbounded font-semibold">Host an event</div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white"><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="p-4 space-y-4">
          <input data-testid="event-title" placeholder="Title" value={form.title} onChange={(e) => setF("title", e.target.value)}
            className="w-full bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00]" />
          <textarea data-testid="event-description" placeholder="Describe the vibe, what people can expect..." rows={4}
            value={form.description} onChange={(e) => setF("description", e.target.value)}
            className="w-full bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm resize-none" />
          <div className="grid grid-cols-2 gap-3">
            <select data-testid="event-category" value={form.category} onChange={(e) => setF("category", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm">
              {CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
            <label className="btn-ghost !py-3 cursor-pointer text-center flex items-center justify-center gap-2 text-xs">
              {uploading ? <Loader2 size={14} className="animate-spin" /> : (form.cover_image ? "Change cover" : "Cover image")}
              <input data-testid="event-cover" type="file" accept="image/*" className="hidden"
                onChange={(e) => upload(e.target.files?.[0])} />
            </label>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input data-testid="event-address" placeholder="Address" value={form.address} onChange={(e) => setF("address", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
            <input data-testid="event-city" placeholder="City" value={form.city} onChange={(e) => setF("city", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
          </div>
          <button type="button" data-testid="event-geocode" onClick={geocode}
            className="btn-ghost !py-2 !text-xs w-full flex items-center justify-center gap-2">
            {geocoding ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
            Find coordinates from address
          </button>
          <div className="grid grid-cols-2 gap-3">
            <input data-testid="event-lat" placeholder="Latitude" value={form.lat} onChange={(e) => setF("lat", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
            <input data-testid="event-lng" placeholder="Longitude" value={form.lng} onChange={(e) => setF("lng", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-zinc-500 mb-1">Start</div>
              <input data-testid="event-start" type="datetime-local" value={form.start_at} onChange={(e) => setF("start_at", e.target.value)}
                className="w-full bg-white/[0.03] border border-white/12 px-3 py-2.5 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
            </div>
            <div>
              <div className="text-xs text-zinc-500 mb-1">End (optional)</div>
              <input data-testid="event-end" type="datetime-local" value={form.end_at} onChange={(e) => setF("end_at", e.target.value)}
                className="w-full bg-white/[0.03] border border-white/12 px-3 py-2.5 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input data-testid="event-free" type="checkbox" checked={form.is_free} onChange={(e) => setF("is_free", e.target.checked)} />
            Free event
          </label>
          {!form.is_free && (
            <input data-testid="event-price" type="number" step="0.01" placeholder="Ticket price"
              value={form.ticket_price} onChange={(e) => setF("ticket_price", e.target.value)}
              className="w-full bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
          )}
          <button data-testid="event-submit" type="submit" disabled={saving}
            className="btn-lime w-full !py-3 flex items-center justify-center gap-2">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            Create event
          </button>
        </form>
      </div>
    </div>
  );
}
