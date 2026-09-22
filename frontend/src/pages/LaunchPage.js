import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, thumbUrl, copyText } from "../api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Calendar, MapPin, Ticket, Share2, Download, Users, ArrowRight, Sparkles } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;
const ORIGIN = window.location.origin;

export default function LaunchPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const [ev, setEv] = useState(null);
  const [busy, setBusy] = useState(false);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    api.get(`/events/${id}`).then((r) => setEv(r.data)).catch(() => setMissing(true));
  }, [id, user?.id]);

  const claim = async () => {
    if (!user) { nav(`/register?next=/launch/${id}`); return; }
    setBusy(true);
    try {
      if (!ev.is_free && !ev.rsvped) {
        const r = await api.post(`/payments/events/${id}/ticket`, { origin_url: ORIGIN });
        if (r.data.checkout_url) { window.location.href = r.data.checkout_url; return; }
      }
      if (!ev.rsvped) {
        const r = await api.post(`/events/${id}/rsvp`, {});
        setEv((e) => ({ ...e, rsvped: r.data.rsvped, rsvp_count: r.data.count }));
        toast.success("You're in — your QR ticket is in Tickets");
      }
      nav("/tickets");
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const share = async () => {
    const url = `${ORIGIN}/launch/${id}`;
    if (navigator.share) { try { await navigator.share({ title: ev.title, url }); return; } catch {} }
    copyText(url); toast.success("Link copied");
  };

  if (missing) return <div className="py-32 text-center label-caps text-zinc-500">This event isn't available.</div>;
  if (!ev) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;

  const when = new Date(ev.start_at);
  const loc = ev.location || {};
  const where = [ev.venue, loc.address, loc.city].filter(Boolean).join(", ");
  const isHost = user && (user.id === ev.host_id || user.role === "admin");
  const full = ev.capacity && ev.rsvp_count >= ev.capacity;

  return (
    <div data-testid="launch-page" className="relative">
      <div className="relative min-h-[70vh] flex items-end overflow-hidden">
        {ev.cover_image && <img src={thumbUrl(ev.cover_image, 960)} alt="" className="absolute inset-0 w-full h-full object-cover opacity-50" />}
        <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0C] via-[#0A0A0C]/60 to-transparent" />
        <div className="relative max-w-5xl mx-auto px-6 md:px-12 pb-14 pt-32 w-full">
          <div className="label-caps text-[#CCFF00] flex items-center gap-2"><Sparkles size={12} /> {(ev.category || "event").replace(/_/g, " ")} · {ev.is_free ? "Free entry" : `$${Number(ev.ticket_price).toLocaleString()}`}</div>
          <h1 className="font-anton text-5xl sm:text-7xl lg:text-[7rem] uppercase leading-[0.9] mt-4 max-w-4xl" data-testid="launch-title">{ev.title}</h1>
          <div className="flex flex-wrap gap-6 mt-8 text-sm text-zinc-200">
            <span className="flex items-center gap-2" data-testid="launch-when"><Calendar size={16} className="text-[#CCFF00]" /> {when.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })} · {when.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
            {where && <span className="flex items-center gap-2" data-testid="launch-where"><MapPin size={16} className="text-[#FF4D4D]" /> {where}</span>}
            <span className="flex items-center gap-2"><Users size={16} className="text-[#7C3AED]" /> {ev.rsvp_count || 0} going{ev.capacity ? ` · ${ev.capacity} spots` : ""}</span>
          </div>
          <div className="flex flex-wrap gap-3 mt-10">
            <button data-testid="launch-claim-btn" onClick={claim} disabled={busy || ev.cancelled || (full && !ev.rsvped)}
              className="btn-lime !px-8 !py-4 text-sm flex items-center gap-2">
              <Ticket size={16} /> {ev.cancelled ? "Event cancelled" : ev.rsvped ? "You're in — view ticket" : full ? "Sold out" : ev.is_free ? "Get my free ticket" : `Get ticket · $${Number(ev.ticket_price).toLocaleString()}`}
            </button>
            <button data-testid="launch-share-btn" onClick={share} className="btn-ghost !px-6 !py-4 text-sm flex items-center gap-2"><Share2 size={16} /> Share</button>
            <a data-testid="launch-poster-btn" href={`${API}/api/events/${id}/poster.png`} download={`artcore-flyer-${id.slice(0, 8)}.png`} target="_blank" rel="noreferrer"
              className="btn-ghost !px-6 !py-4 text-sm flex items-center gap-2"><Download size={16} /> {isHost ? "Download flyer poster" : "Poster"}</a>
          </div>
          {!user && <div className="text-xs text-zinc-500 mt-3">Free account in 20 seconds — your QR ticket lands in your wallet instantly.</div>}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 md:px-12 py-16 grid md:grid-cols-5 gap-12">
        <div className="md:col-span-3">
          <div className="label-caps text-zinc-500 mb-4">About this event</div>
          <p className="text-zinc-200 leading-relaxed whitespace-pre-line text-base">{ev.description}</p>
          {ev.ticket_info && <p className="text-sm text-zinc-400 mt-4 border-l-2 border-[#CCFF00]/40 pl-4">{ev.ticket_info}</p>}
          <Link to={`/events/${id}`} className="inline-flex items-center gap-2 text-sm text-[#CCFF00] mt-8 hover:underline" data-testid="launch-full-details">Full event page <ArrowRight size={14} /></Link>
        </div>
        <div className="md:col-span-2 space-y-4">
          <div className="glass-card p-5 rounded-sm">
            <div className="label-caps text-zinc-500">Hosted by</div>
            <Link to={`/host/${ev.host_id}`} className="font-unbounded font-semibold mt-1 block hover:text-[#CCFF00]" data-testid="launch-host">{ev.organizer || ev.host_name || "Art Core artist"}</Link>
          </div>
          <div className="glass-card p-5 rounded-sm">
            <div className="label-caps text-[#CCFF00]">What is Art Core?</div>
            <p className="text-sm text-zinc-300 mt-2 leading-relaxed">A marketplace and community built only for artists — buy originals directly, follow studios, bid in live auctions, and find art events near campus. Artists keep 92%+ of every sale.</p>
            <Link to="/explore" className="text-xs text-[#CCFF00] mt-3 inline-block hover:underline">Explore the gallery →</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
