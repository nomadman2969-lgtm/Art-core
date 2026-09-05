import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Calendar, Users, MapPin, ArrowLeft, Trash2, Loader2, QrCode, CheckCircle2 } from "lucide-react";
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
  const [ticket, setTicket] = useState(null);
  const [showTicket, setShowTicket] = useState(false);

  const load = () => {
    setLoading(true);
    api.get(`/events/${id}`).then((r) => setEv(r.data)).catch(() => setEv(null)).finally(() => setLoading(false));
    api.get(`/events/${id}/attendees`).then((r) => setAttendees(r.data)).catch(() => setAttendees([]));
  };
  useEffect(() => { load(); }, [id]);

  // Load ticket details when the user has RSVP'd
  useEffect(() => {
    if (ev?.rsvped && !ev.cancelled) {
      api.get(`/events/${id}/my-ticket`).then((r) => setTicket(r.data)).catch(() => setTicket(null));
    } else {
      setTicket(null);
    }
  }, [ev?.rsvped, ev?.cancelled, id]);

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

          {/* Attendee's ticket QR */}
          {ticket && !ev.cancelled && (
            <div className="border border-white/8 rounded-sm p-4 bg-[#121214]" data-testid="my-ticket-card">
              <div className="flex items-center justify-between mb-2">
                <div className="label-caps text-[#CCFF00] flex items-center gap-1">
                  <QrCode size={12} /> Your Ticket
                </div>
                {ticket.checked_in && (
                  <div className="label-caps text-[#CCFF00] flex items-center gap-1 text-xs">
                    <CheckCircle2 size={12} /> Checked in
                  </div>
                )}
              </div>
              {showTicket ? (
                <>
                  {ticket.qr_image && (
                    <img
                      src={ticket.qr_image}
                      alt="Ticket QR"
                      data-testid="ticket-qr-img"
                      className="w-full max-w-[220px] mx-auto bg-white p-2 rounded-sm my-2" />
                  )}
                  <div className="text-xs text-zinc-400 text-center">
                    {ticket.user_name} · {ticket.paid ? `$${ticket.amount}` : "Free"}
                  </div>
                  <div className="text-[10px] text-zinc-600 text-center mt-1 break-all font-mono">
                    ID {ticket.rsvp_id.slice(0, 8)}
                  </div>
                  <button data-testid="hide-ticket-btn" onClick={() => setShowTicket(false)}
                    className="btn-ghost w-full mt-3 !py-2 text-xs">Hide QR</button>
                </>
              ) : (
                <button data-testid="show-ticket-btn" onClick={() => setShowTicket(true)}
                  className="btn-lime w-full !py-2 flex items-center justify-center gap-2 text-xs">
                  <QrCode size={14} /> Show ticket QR
                </button>
              )}
            </div>
          )}

          {/* Host check-in scanner */}
          {isHost && !ev.cancelled && (
            <HostCheckIn eventId={id} onCheckedIn={() => api.get(`/events/${id}/attendees`).then((r) => setAttendees(r.data))} />
          )}
        </aside>
      </div>
    </div>
  );
}

function HostCheckIn({ eventId, onCheckedIn }) {
  const [payload, setPayload] = useState("");
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState(null);
  const [mode, setMode] = useState("scan"); // scan | manual
  const [scannerReady, setScannerReady] = useState(false);
  const scannerRef = React.useRef(null);
  const html5QrRef = React.useRef(null);
  const inFlightRef = React.useRef(false);

  const doCheckIn = async (rawPayload) => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setBusy(true);
    try {
      const r = await api.post(`/events/${eventId}/check-in`, { qr_payload: rawPayload.trim() });
      setLast({ name: r.data.user_name, already: !!r.data.already });
      toast.success(r.data.already ? `${r.data.user_name} was already checked in` : `Checked in ${r.data.user_name}`);
      onCheckedIn?.();
    } catch (er) {
      const msg = er?.response?.data?.detail || "Invalid ticket";
      setLast({ name: msg, already: false, error: true });
      toast.error(msg);
    }
    setTimeout(() => { inFlightRef.current = false; }, 1500);
    setBusy(false);
  };

  // Attach camera scanner
  useEffect(() => {
    if (mode !== "scan") return;
    let cancelled = false;
    (async () => {
      try {
        const { Html5Qrcode } = await import("html5-qrcode");
        if (cancelled) return;
        if (!scannerRef.current) return;
        const inst = new Html5Qrcode(scannerRef.current.id);
        html5QrRef.current = inst;
        await inst.start(
          { facingMode: "environment" },
          { fps: 10, qrbox: { width: 220, height: 220 } },
          (decodedText) => { doCheckIn(decodedText); },
          () => { /* ignore per-frame decode errors */ },
        );
        setScannerReady(true);
      } catch (e) {
        setScannerReady(false);
        // Camera denied / unavailable — offer manual fallback
        setMode("manual");
        toast("Camera unavailable — paste ticket code instead");
      }
    })();
    return () => {
      cancelled = true;
      const inst = html5QrRef.current;
      if (inst) {
        inst.stop().then(() => inst.clear()).catch(() => null);
        html5QrRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const submitManual = async (e) => {
    e?.preventDefault?.();
    if (!payload.trim()) return;
    await doCheckIn(payload);
    setPayload("");
  };

  return (
    <div className="border border-white/8 rounded-sm p-4 bg-[#121214]" data-testid="host-checkin">
      <div className="flex items-center justify-between mb-2">
        <div className="label-caps text-[#7C3AED] flex items-center gap-1"><QrCode size={12} /> Door Check-in</div>
        <div className="flex gap-1">
          <button data-testid="checkin-mode-scan" onClick={() => setMode("scan")}
            className={`label-caps text-[10px] px-2 py-0.5 rounded-sm ${mode === "scan" ? "bg-[#CCFF00] text-black" : "border border-white/10 text-zinc-400"}`}>Scan</button>
          <button data-testid="checkin-mode-manual" onClick={() => setMode("manual")}
            className={`label-caps text-[10px] px-2 py-0.5 rounded-sm ${mode === "manual" ? "bg-[#CCFF00] text-black" : "border border-white/10 text-zinc-400"}`}>Paste</button>
        </div>
      </div>

      {mode === "scan" ? (
        <>
          <div className="text-xs text-zinc-500 mb-2">Point the camera at the attendee's ticket QR.</div>
          <div ref={scannerRef} id="host-qr-scanner" data-testid="qr-scanner" className="w-full aspect-square bg-black rounded-sm overflow-hidden" />
          {!scannerReady && <div className="text-[11px] text-zinc-500 mt-2">Requesting camera...</div>}
        </>
      ) : (
        <>
          <div className="text-xs text-zinc-500 mb-2">Paste a ticket QR payload below.</div>
          <form onSubmit={submitManual} className="flex gap-2">
            <input data-testid="checkin-input" value={payload} onChange={(e) => setPayload(e.target.value)}
              placeholder="artcore:ticket:..."
              className="flex-1 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 text-xs outline-none focus:border-[#CCFF00]" />
            <button data-testid="checkin-submit" type="submit" disabled={busy || !payload.trim()}
              className="btn-lime !py-2 !px-3 flex items-center gap-1 text-xs">
              {busy ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
            </button>
          </form>
        </>
      )}

      {last && (
        <div data-testid="checkin-last" className="text-xs mt-3" style={{ color: last.error ? "#FF4D4D" : last.already ? "#F5A623" : "#CCFF00" }}>
          {last.error ? "✕" : last.already ? "⚠ Already in" : "✓ Checked in"} · {last.name}
        </div>
      )}
    </div>
  );
}

