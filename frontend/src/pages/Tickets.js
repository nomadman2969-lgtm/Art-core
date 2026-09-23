import { WalletPassButton } from "../components/events/WalletPassButton";
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "../api";
import { toast } from "sonner";
import { Ticket, Calendar, MapPin, QrCode, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { CalendarSubscribe } from "../components/CalendarSubscribe";
import { EmptyState } from "../components/EmptyState";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));
const catColor = { gallery_opening: "#D4AF37", pop_up: "#FF4D4D", festival: "#FF6EC7", meetup: "#7C3AED", workshop: "#00E5FF", live_painting: "#F5A623", virtual: "#CCFF00", market: "#00E5FF" };

export default function Tickets() {
  const [tickets, setTickets] = useState(null);
  const [tab, setTab] = useState("upcoming"); // upcoming | past
  const [openQr, setOpenQr] = useState(null); // ticket obj

  const load = () => {
    api.get(`/events/mine/tickets?upcoming_only=${tab === "upcoming"}`)
      .then((r) => setTickets(r.data))
      .catch(() => setTickets([]));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [tab]);

  if (tickets === null) return <div className="py-32 text-center label-caps text-zinc-500">Loading tickets...</div>;

  return (
    <div data-testid="tickets-page" className="max-w-3xl mx-auto px-4 md:px-6 pt-10 pb-32">
      <div className="mb-6 flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="label-caps text-[#CCFF00]"><Ticket size={12} className="inline mr-2" /> My Wallet</div>
          <h1 className="font-anton text-5xl md:text-6xl uppercase mt-3">Tickets</h1>
          <div className="text-zinc-500 mt-2">Every event you're going to — QR code always in your pocket.</div>
        </div>
        <CalendarSubscribe />
      </div>

      <div className="flex gap-1 mb-8 border-b border-white/8">
        {[["upcoming", "Upcoming"], ["past", "Past & Cancelled"]].map(([k, l]) => (
          <button key={k} data-testid={`tickets-tab-${k}`} onClick={() => setTab(k)}
            className={`label-caps text-xs px-4 py-3 border-b-2 ${tab === k ? "border-[#CCFF00] text-white" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}>
            {l}
          </button>
        ))}
      </div>

      {tickets.length === 0 ? (
        <EmptyState icon="ticket" title={tab === "upcoming" ? "No upcoming tickets" : "No past events yet"} body="RSVP to any event and your QR ticket appears here — show it at the door, add it to your calendar, or gift it to a friend." cta="Find events near you" to="/events" testId="tickets-empty" />
      ) : (
        <div className="space-y-3">
          {tickets.map((t) => (
            <TicketCard key={t.rsvp_id} t={t} onOpen={() => setOpenQr(t)} />
          ))}
        </div>
      )}

      {openQr && <TicketQRModal ticket={openQr} onClose={() => setOpenQr(null)} />}
    </div>
  );
}

function TicketCard({ t, onOpen }) {
  const e = t.event;
  const color = catColor[e.category] || "#CCFF00";
  const isCancelled = e.cancelled;
  const isPast = new Date(e.start_at) < new Date();
  return (
    <div data-testid={`ticket-${t.rsvp_id}`} className="border border-white/8 rounded-sm overflow-hidden bg-[#121214] flex flex-col md:flex-row">
      <Link to={`/events/${e.id}`} className="md:w-40 h-32 md:h-auto flex-shrink-0 relative overflow-hidden">
        {e.cover_image ? (
          <img src={resolveImg(e.cover_image)} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${color}30, #0A0A0C)` }}>
            <MapPin size={22} className="text-white/40" />
          </div>
        )}
        <div className="absolute top-2 left-2 label-caps text-[10px] px-1.5 py-0.5 rounded-sm bg-black/70">{(e.category || "").replace(/_/g, " ")}</div>
      </Link>
      <div className="flex-1 p-4 flex flex-col justify-between">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <Link to={`/events/${e.id}`} className="font-anton text-2xl uppercase leading-tight hover:text-[#CCFF00]">{e.title}</Link>
            {t.paid && !t.refunded && <span className="label-caps text-[10px] px-1.5 py-0.5 rounded-sm bg-[#F5A623]/20 text-[#F5A623]">${t.amount}</span>}
            {t.refunded && <span className="label-caps text-[10px] px-1.5 py-0.5 rounded-sm bg-[#FF4D4D]/20 text-[#FF4D4D] flex items-center gap-1"><XCircle size={10} /> Refunded</span>}
            {t.checked_in && <span className="label-caps text-[10px] px-1.5 py-0.5 rounded-sm bg-[#CCFF00]/20 text-[#CCFF00] flex items-center gap-1"><CheckCircle2 size={10} /> Checked in</span>}
            {isCancelled && <span className="label-caps text-[10px] px-1.5 py-0.5 rounded-sm bg-[#FF4D4D]/20 text-[#FF4D4D]">Cancelled</span>}
          </div>
          <div className="text-xs text-zinc-400 mt-1 flex items-center gap-1">
            <Calendar size={11} /> {new Date(e.start_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
          </div>
          <div className="text-xs text-zinc-500 flex items-center gap-1">
            <MapPin size={11} /> {e.location?.city || e.location?.address || "TBA"}
          </div>
        </div>
        {!isCancelled && !t.refunded && !isPast && (
          <div className="mt-3">
            <button
              data-testid={`ticket-qr-btn-${t.rsvp_id}`}
              onClick={onOpen}
              className="btn-lime !py-1.5 !px-3 text-xs inline-flex items-center gap-1.5">
              <QrCode size={12} /> Show QR
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function TicketQRModal({ ticket, onClose }) {
  const [qrData, setQrData] = useState(null);

  useEffect(() => {
    api.get(`/events/${ticket.event.id}/my-ticket`)
      .then((r) => setQrData(r.data))
      .catch(() => { toast.error("Couldn't load QR"); onClose(); });
    // eslint-disable-next-line
  }, [ticket.rsvp_id]);

  return (
    <div onClick={onClose} data-testid="ticket-qr-modal"
      className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
      <div onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-sm p-6 max-w-sm w-full text-black">
        <div className="text-black">
          <div className="text-xs uppercase tracking-wider text-zinc-500">Art Core Ticket</div>
          <div className="font-anton text-2xl uppercase mt-1">{ticket.event.title}</div>
          <div className="text-xs text-zinc-500 mt-1">
            {new Date(ticket.event.start_at).toLocaleString()} · {ticket.event.location?.city || ticket.event.location?.address || ""}
          </div>
        </div>
        {qrData?.qr_image ? (
          <img src={qrData.qr_image} alt="QR" className="w-full my-4" data-testid="wallet-qr-img" />
        ) : (
          <div className="w-full aspect-square my-4 flex items-center justify-center bg-zinc-100">
            <Loader2 className="animate-spin text-zinc-500" />
          </div>
        )}
        <div className="text-xs text-zinc-600 text-center">{qrData?.user_name || "Attendee"}</div>
        <div className="text-[10px] text-zinc-400 text-center font-mono mt-1">ID {ticket.rsvp_id.slice(0, 8)}</div>
        <WalletPassButton eventId={ticket.event.id} className="w-full !py-2 !text-black !border-black/20" />
        <button data-testid="close-ticket-qr" onClick={onClose}
          className="mt-4 w-full bg-black text-white py-2 label-caps text-xs">Close</button>
      </div>
    </div>
  );
}
