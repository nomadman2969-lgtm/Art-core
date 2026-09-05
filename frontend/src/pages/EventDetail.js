import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Calendar, Users, MapPin, ArrowLeft, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, fileUrl, ORIGIN } from "../api";
import { useAuth } from "../context/AuthContext";

const catColor = { gallery_opening: "#D4AF37", pop_up: "#FF4D4D", festival: "#FF6EC7", meetup: "#7C3AED", workshop: "#00E5FF", live_painting: "#F5A623", virtual: "#CCFF00", market: "#00E5FF" };
const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export default function EventDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [ev, setEv] = useState(null);
  const [loading, setLoading] = useState(true);
  const [attendees, setAttendees] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoading(true);
    api.get(`/events/${id}`).then((r) => setEv(r.data)).catch(() => setEv(null)).finally(() => setLoading(false));
    api.get(`/events/${id}/attendees`).then((r) => setAttendees(r.data)).catch(() => setAttendees([]));
  };
  useEffect(() => { load(); }, [id]);

  const toggleRsvp = async () => {
    setBusy(true);
    try {
      // Paid event → route to Stripe checkout for buying a ticket
      if (!ev.is_free && !ev.rsvped) {
        const r = await api.post(`/payments/events/${id}/ticket`, { origin_url: ORIGIN });
        if (r.data.checkout_url) {
          window.location.href = r.data.checkout_url;
          return;
        }
      }
      const r = await api.post(`/events/${id}/rsvp`, {});
      setEv((e) => ({ ...e, rsvped: r.data.rsvped, rsvp_count: r.data.count }));
      toast.success(r.data.rsvped ? "You're going" : "RSVP removed");
      load();
    } catch (er) {
      toast.error(er?.response?.data?.detail || "Failed");
    }
    setBusy(false);
  };

  const cancelEvent = async () => {
    if (!confirm("Cancel this event? All attendees will be notified.")) return;
    setBusy(true);
    try {
      await api.delete(`/events/${id}`);
      toast.success("Cancelled");
      nav("/events");
    } catch { toast.error("Failed"); }
    setBusy(false);
  };

  if (loading) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;
  if (!ev) return <div className="py-32 text-center label-caps text-zinc-500">Event not found</div>;

  const isHost = user?.id === ev.host?.id || user?.role === "admin";
  const color = catColor[ev.category] || "#CCFF00";

  return (
    <div data-testid="event-detail" className="max-w-5xl mx-auto px-4 md:px-6 pt-8 pb-32">
      <Link to="/events" className="label-caps text-zinc-500 hover:text-[#CCFF00] mb-4 inline-flex items-center gap-1"><ArrowLeft size={12} /> Events</Link>

      {ev.cancelled && (
        <div className="border border-[#FF4D4D]/40 bg-[#FF4D4D]/10 text-[#FF4D4D] rounded-sm p-3 mb-4 label-caps text-xs text-center">
          This event was cancelled
        </div>
      )}

      {ev.cover_image ? (
        <img src={resolveImg(ev.cover_image)} alt={ev.title} className="w-full max-h-[420px] object-cover rounded-sm mb-6" />
      ) : (
        <div className="w-full h-56 rounded-sm mb-6 flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${color}40, #0A0A0C)` }}>
          <MapPin size={48} className="text-white/40" />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-[1fr_320px] gap-8">
        <div>
          <span className="label-caps text-xs px-2 py-1 rounded-sm" style={{ background: `${color}22`, color }}>{(ev.category || "").replace(/_/g, " ")}</span>
          <h1 className="font-anton text-4xl md:text-5xl uppercase mt-3 leading-tight">{ev.title}</h1>
          <div className="flex items-center gap-6 text-sm text-zinc-400 mt-3 flex-wrap">
            <div className="flex items-center gap-1"><Calendar size={12} /> {new Date(ev.start_at).toLocaleString()}</div>
            {ev.end_at && <div className="flex items-center gap-1">— {new Date(ev.end_at).toLocaleString()}</div>}
            <div className="flex items-center gap-1"><Users size={12} /> {ev.rsvp_count} going</div>
          </div>
          <div className="text-zinc-300 whitespace-pre-wrap mt-6 leading-relaxed">{ev.description}</div>
          {ev.host?.id && (
            <div className="mt-8 pt-6 border-t border-white/8">
              <div className="label-caps text-zinc-500 mb-2">Hosted by</div>
              <Link to={`/artist/${ev.host.id}`} className="flex items-center gap-3 hover:text-[#CCFF00]">
                <div className="w-10 h-10 rounded-full bg-[#7C3AED]/30 flex items-center justify-center font-anton">
                  {ev.host.name?.[0]?.toUpperCase()}
                </div>
                <div>
                  <div className="font-unbounded font-semibold">{ev.host.name}</div>
                  <div className="text-xs text-zinc-500 label-caps">{ev.host.role}</div>
                </div>
              </Link>
            </div>
          )}
          {attendees.length > 0 && (
            <div className="mt-8 pt-6 border-t border-white/8">
              <div className="label-caps text-zinc-500 mb-3">{attendees.length} attending</div>
              <div className="flex flex-wrap gap-2">
                {attendees.slice(0, 24).map((a) => (
                  <div key={a.id} className="text-xs px-3 py-1.5 border border-white/8 rounded-full">{a.user_name}</div>
                ))}
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <div className="border border-white/8 rounded-sm p-4 bg-[#121214]">
            <div className="label-caps text-zinc-500 mb-2">Price</div>
            <div className="font-anton text-3xl">{ev.is_free ? "FREE" : `$${ev.ticket_price}`}</div>
            {!ev.cancelled && (
              <button data-testid="rsvp-btn" onClick={toggleRsvp} disabled={busy}
                className={`w-full mt-4 !py-3 ${ev.rsvped ? "btn-ghost" : "btn-lime"}`}>
                {busy ? <Loader2 size={14} className="animate-spin inline" /> :
                  ev.rsvped ? "Cancel RSVP" :
                  ev.is_free ? "RSVP" : `Get Ticket · $${ev.ticket_price}`}
              </button>
            )}
            {ev.max_capacity && (
              <div className="text-xs text-zinc-500 mt-2 text-center">
                {ev.rsvp_count}/{ev.max_capacity} spots
              </div>
            )}
          </div>

          <div className="border border-white/8 rounded-sm overflow-hidden h-64">
            <MapContainer center={[ev.location.lat, ev.location.lng]} zoom={13} scrollWheelZoom={false} style={{ height: "100%", width: "100%", background: "#0A0A0C" }}>
              <TileLayer
                attribution='&copy; OSM contributors'
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                className="grayscale contrast-125"
              />
              <Marker position={[ev.location.lat, ev.location.lng]}>
                <Popup>{ev.title}</Popup>
              </Marker>
            </MapContainer>
          </div>
          <div className="text-xs text-zinc-400">
            <MapPin size={11} className="inline mr-1" />
            {[ev.location.address, ev.location.city].filter(Boolean).join(", ") || "Location TBA"}
          </div>

          {isHost && !ev.cancelled && (
            <button data-testid="cancel-event-btn" onClick={cancelEvent} disabled={busy}
              className="btn-ghost !text-[#FF4D4D] !border-[#FF4D4D]/40 w-full flex items-center justify-center gap-2 text-xs">
              <Trash2 size={12} /> Cancel event
            </button>
          )}
        </aside>
      </div>
    </div>
  );
}
