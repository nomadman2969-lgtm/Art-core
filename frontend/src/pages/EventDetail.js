import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Calendar, Users, MapPin, ArrowLeft, Trash2, Loader2, QrCode, CheckCircle2, Clock, TrendingUp, DollarSign, X } from "lucide-react";
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
  const [waitlistPos, setWaitlistPos] = useState(null); // {on_waitlist, position}
  const [analytics, setAnalytics] = useState(null);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

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
    const wholeSeries = ev.series_id ? confirm("This event is part of a series. Cancel the ENTIRE remaining series?") : false;
    const oneOnly = !ev.series_id ? confirm("Cancel this event? All attendees will be notified and paid tickets refunded.") : true;
    if (!oneOnly && !wholeSeries) return;
    setBusy(true);
    try {
      await api.delete(`/events/${id}${wholeSeries ? "?cancel_series=true" : ""}`);
      toast.success(wholeSeries ? "Whole series cancelled" : "Cancelled");
      nav("/events");
    } catch { toast.error("Failed"); }
    setBusy(false);
  };

  const toggleWaitlist = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/events/${id}/waitlist`, {});
      setWaitlistPos(r.data);
      toast.success(r.data.on_waitlist ? `You're #${r.data.position} on the waitlist` : "Removed from waitlist");
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const loadAnalytics = async () => {
    try {
      const r = await api.get(`/events/${id}/analytics`);
      setAnalytics(r.data);
      setShowAnalytics(true);
    } catch { toast.error("Couldn't load analytics"); }
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
            {ev.series_id && (
              <div className="text-xs text-[#F5A623] mt-1 flex items-center gap-1">
                <Clock size={11} /> Session {ev.series_seq}/{ev.series_total} in this series
              </div>
            )}
            {ev.max_capacity && (
              <div className="text-xs text-zinc-500 mt-1">
                {ev.rsvp_count}/{ev.max_capacity} spots · {Math.max(0, ev.max_capacity - ev.rsvp_count)} left
              </div>
            )}

            {!ev.cancelled && (
              <>
                {(ev.max_capacity && ev.rsvp_count >= ev.max_capacity && !ev.rsvped) ? (
                  <button data-testid="waitlist-btn" onClick={toggleWaitlist} disabled={busy}
                    className={`w-full mt-4 !py-3 ${waitlistPos?.on_waitlist ? "btn-ghost" : "btn-violet"}`}>
                    {busy ? <Loader2 size={14} className="animate-spin inline" /> :
                      waitlistPos?.on_waitlist ? `On waitlist · #${waitlistPos.position} · Leave` : "Join Waitlist"}
                  </button>
                ) : (
                  <button data-testid="rsvp-btn" onClick={toggleRsvp} disabled={busy}
                    className={`w-full mt-4 !py-3 ${ev.rsvped ? "btn-ghost" : "btn-lime"}`}>
                    {busy ? <Loader2 size={14} className="animate-spin inline" /> :
                      ev.rsvped ? "Cancel RSVP" :
                      ev.is_free ? "RSVP" : `Get Ticket · $${ev.ticket_price}`}
                  </button>
                )}
              </>
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
            <>
              <button data-testid="edit-event-btn" onClick={() => setShowEdit(true)}
                className="btn-ghost w-full flex items-center justify-center gap-2 text-xs">
                Edit event
              </button>
              <button data-testid="show-analytics-btn" onClick={loadAnalytics}
                className="btn-ghost !text-[#CCFF00] !border-[#CCFF00]/40 w-full flex items-center justify-center gap-2 text-xs">
                <TrendingUp size={12} /> View analytics
              </button>
              <button data-testid="cancel-event-btn" onClick={cancelEvent} disabled={busy}
                className="btn-ghost !text-[#FF4D4D] !border-[#FF4D4D]/40 w-full flex items-center justify-center gap-2 text-xs">
                <Trash2 size={12} /> {ev.series_id ? "Cancel event / series" : "Cancel event"}
              </button>
            </>
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
      {showAnalytics && analytics && (
        <AnalyticsModal analytics={analytics} onClose={() => setShowAnalytics(false)} />
      )}
      {showEdit && (
        <EditEventModal ev={ev} onClose={() => setShowEdit(false)} onSaved={() => { setShowEdit(false); load(); }} />
      )}
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


function AnalyticsModal({ analytics, onClose }) {
  const curve = analytics.rsvp_curve || [];
  const max = Math.max(1, ...curve.map((c) => c.count));

  const downloadCsv = async (kind) => {
    try {
      const r = await api.get(`/events/${analytics.event_id}/analytics.csv?kind=${kind}`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([r.data], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `artcore_${kind}_${analytics.event_id.slice(0, 6)}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`${kind === "attendees" ? "Attendee list" : "Revenue report"} downloaded`);
    } catch { toast.error("Download failed"); }
  };

  return (
    <div onClick={onClose} data-testid="analytics-modal"
      className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 md:p-6 overflow-y-auto">
      <div onClick={(e) => e.stopPropagation()} className="bg-[#121214] border border-white/10 rounded-sm w-full max-w-2xl my-auto">
        <div className="flex items-center justify-between p-4 border-b border-white/8">
          <div className="flex items-center gap-2">
            <TrendingUp size={14} className="text-[#CCFF00]" />
            <div className="label-caps">Event Analytics</div>
          </div>
          <div className="flex items-center gap-2">
            <button data-testid="csv-attendees" onClick={() => downloadCsv("attendees")}
              className="label-caps text-[10px] px-2 py-1 border border-white/12 rounded-sm hover:border-[#CCFF00] hover:text-[#CCFF00]">
              CSV · Attendees
            </button>
            <button data-testid="csv-revenue" onClick={() => downloadCsv("revenue")}
              className="label-caps text-[10px] px-2 py-1 border border-white/12 rounded-sm hover:border-[#CCFF00] hover:text-[#CCFF00]">
              CSV · Revenue
            </button>
            <button onClick={onClose} className="text-zinc-500 hover:text-white ml-1"><X size={18} /></button>
          </div>
        </div>
        <div className="p-6 space-y-6">
          <div>
            <div className="font-anton text-2xl uppercase leading-tight">{analytics.title}</div>
            <div className="text-xs text-zinc-500 mt-1">Metrics update every page load.</div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatBox label="Total RSVPs" value={analytics.total_rsvps} accent="#CCFF00" />
            <StatBox label="Check-in rate" value={`${analytics.check_in_rate}%`} accent="#7C3AED" sub={`${analytics.checked_in} in`} />
            <StatBox label="Paid tickets" value={analytics.paid_rsvps} accent="#F5A623" sub={`${analytics.refunded_rsvps} refunded`} />
            <StatBox label="Waitlist" value={analytics.waitlist} accent="#FF4D4D" />
          </div>

          {analytics.paid_rsvps > 0 && (
            <div className="border border-white/8 rounded-sm p-4">
              <div className="label-caps text-zinc-500 mb-3"><DollarSign size={11} className="inline mr-1" /> Revenue</div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <div className="text-[10px] uppercase text-zinc-500 tracking-wider">Gross</div>
                  <div className="font-anton text-xl text-white">${analytics.revenue_gross.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase text-zinc-500 tracking-wider">Platform fee</div>
                  <div className="font-anton text-xl text-[#F5A623]">${analytics.platform_fee.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase text-zinc-500 tracking-wider">Net to you</div>
                  <div className="font-anton text-xl text-[#CCFF00]">${analytics.net_to_host.toFixed(2)}</div>
                </div>
              </div>
              {analytics.revenue_refunded > 0 && (
                <div className="text-xs text-[#FF4D4D] mt-2">${analytics.revenue_refunded.toFixed(2)} refunded</div>
              )}
            </div>
          )}

          {analytics.capacity && (
            <div className="border border-white/8 rounded-sm p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="label-caps text-zinc-500">Fill rate</div>
                <div className="font-anton text-lg">{analytics.fill_rate}%</div>
              </div>
              <div className="w-full h-2 bg-white/[0.06] rounded-sm overflow-hidden">
                <div className="h-full bg-[#CCFF00]" style={{ width: `${Math.min(100, analytics.fill_rate || 0)}%` }} />
              </div>
              <div className="text-xs text-zinc-500 mt-1">{analytics.total_rsvps} / {analytics.capacity} seats</div>
            </div>
          )}

          {curve.length > 1 && (
            <div className="border border-white/8 rounded-sm p-4">
              <div className="label-caps text-zinc-500 mb-3">RSVP Curve</div>
              <div className="flex items-end gap-1 h-24" data-testid="rsvp-curve">
                {curve.map((c) => (
                  <div key={c.date} className="flex-1 flex flex-col justify-end" title={`${c.date}: ${c.count}`}>
                    <div className="w-full rounded-t-sm transition-all"
                      style={{
                        height: `${(c.count / max) * 100}%`,
                        background: c.count === 0 ? "rgba(255,255,255,0.05)" : "#CCFF00",
                        minHeight: "3px",
                      }} />
                  </div>
                ))}
              </div>
              <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
                <span>{curve[0]?.date.slice(5)}</span>
                <span>{curve[curve.length - 1]?.date.slice(5)}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatBox({ label, value, accent, sub }) {
  return (
    <div className="border border-white/8 rounded-sm p-3">
      <div className="text-[10px] uppercase text-zinc-500 tracking-wider">{label}</div>
      <div className="font-anton text-2xl mt-1" style={{ color: accent }}>{value}</div>
      {sub && <div className="text-[10px] text-zinc-500 mt-0.5">{sub}</div>}
    </div>
  );
}


function EditEventModal({ ev, onClose, onSaved }) {
  const [form, setForm] = useState({
    title: ev.title, description: ev.description, category: ev.category,
    address: ev.location?.address || "", city: ev.location?.city || "",
    lat: String(ev.location?.lat ?? ""), lng: String(ev.location?.lng ?? ""),
    start_at: ev.start_at ? ev.start_at.slice(0, 16) : "",
    end_at: ev.end_at ? ev.end_at.slice(0, 16) : "",
    max_capacity: ev.max_capacity || "",
    is_free: !!ev.is_free, ticket_price: ev.ticket_price || "",
    apply_to: "this",
  });
  const [busy, setBusy] = useState(false);
  const setF = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const inSeries = !!ev.series_id;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = {
        title: form.title, description: form.description, category: form.category,
        location: { lat: parseFloat(form.lat), lng: parseFloat(form.lng), address: form.address || null, city: form.city || null },
        is_free: form.is_free,
        ticket_price: form.is_free ? null : parseFloat(form.ticket_price) || 0,
        max_capacity: form.max_capacity ? parseInt(form.max_capacity, 10) : null,
        apply_to: form.apply_to,
      };
      // start/end only when editing single occurrence (backend ignores on series)
      if (form.apply_to === "this") {
        payload.start_at = new Date(form.start_at).toISOString();
        payload.end_at = form.end_at ? new Date(form.end_at).toISOString() : null;
      }
      await api.patch(`/events/${ev.id}`, payload);
      toast.success(form.apply_to === "series" ? "Whole series updated" : "Event updated");
      onSaved?.();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const inputCls = "w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 text-sm outline-none focus:border-[#CCFF00]";

  return (
    <div onClick={onClose} data-testid="edit-event-modal"
      className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 md:p-6 overflow-y-auto">
      <div onClick={(e) => e.stopPropagation()} className="bg-[#121214] border border-white/10 rounded-sm w-full max-w-xl my-auto">
        <div className="flex items-center justify-between p-4 border-b border-white/8">
          <div className="font-unbounded font-semibold">Edit event</div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white"><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="p-4 space-y-3">
          {inSeries && (
            <div className="border border-[#F5A623]/40 bg-[#F5A623]/10 rounded-sm p-3 space-y-2">
              <div className="label-caps text-[#F5A623] text-xs">This event is part of a series</div>
              <div className="flex gap-2">
                <label className="flex items-center gap-2 text-xs">
                  <input data-testid="apply-this" type="radio" name="apply_to" checked={form.apply_to === "this"}
                    onChange={() => setF("apply_to", "this")} />
                  This occurrence only
                </label>
                <label className="flex items-center gap-2 text-xs">
                  <input data-testid="apply-series" type="radio" name="apply_to" checked={form.apply_to === "series"}
                    onChange={() => setF("apply_to", "series")} />
                  Entire series
                </label>
              </div>
            </div>
          )}
          <input data-testid="edit-title" value={form.title} onChange={(e) => setF("title", e.target.value)} placeholder="Title" className={inputCls} />
          <textarea data-testid="edit-description" value={form.description} onChange={(e) => setF("description", e.target.value)} rows={3}
            className={inputCls} />
          <div className="grid grid-cols-2 gap-3">
            <input data-testid="edit-city" value={form.city} onChange={(e) => setF("city", e.target.value)} placeholder="City" className={inputCls} />
            <input data-testid="edit-address" value={form.address} onChange={(e) => setF("address", e.target.value)} placeholder="Address" className={inputCls} />
            <input data-testid="edit-lat" value={form.lat} onChange={(e) => setF("lat", e.target.value)} placeholder="Lat" className={inputCls} />
            <input data-testid="edit-lng" value={form.lng} onChange={(e) => setF("lng", e.target.value)} placeholder="Lng" className={inputCls} />
          </div>
          {form.apply_to === "this" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-zinc-500 mb-1">Start</div>
                <input data-testid="edit-start" type="datetime-local" value={form.start_at}
                  onChange={(e) => setF("start_at", e.target.value)} className={inputCls} />
              </div>
              <div>
                <div className="text-xs text-zinc-500 mb-1">End</div>
                <input data-testid="edit-end" type="datetime-local" value={form.end_at}
                  onChange={(e) => setF("end_at", e.target.value)} className={inputCls} />
              </div>
            </div>
          )}
          <input data-testid="edit-capacity" type="number" min="1" value={form.max_capacity}
            onChange={(e) => setF("max_capacity", e.target.value)} placeholder="Max capacity" className={inputCls} />
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input data-testid="edit-free" type="checkbox" checked={form.is_free}
              onChange={(e) => setF("is_free", e.target.checked)} />
            Free event
          </label>
          {!form.is_free && (
            <input data-testid="edit-price" type="number" step="0.01" placeholder="Ticket price"
              value={form.ticket_price} onChange={(e) => setF("ticket_price", e.target.value)} className={inputCls} />
          )}
          <button data-testid="edit-submit" type="submit" disabled={busy}
            className="btn-lime w-full !py-3 mt-2 flex items-center justify-center gap-2">
            {busy ? <Loader2 size={14} className="animate-spin" /> : null}
            {form.apply_to === "series" ? "Save to whole series" : "Save changes"}
          </button>
        </form>
      </div>
    </div>
  );
}

