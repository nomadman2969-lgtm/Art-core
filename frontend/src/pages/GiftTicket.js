import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Calendar, MapPin, Gift, CheckCircle2, QrCode } from "lucide-react";
import { api, fileUrl } from "../api";
import { useAuth } from "../context/AuthContext";
import { WalletPassButton } from "../components/events/WalletPassButton";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export default function GiftTicket() {
  const { token } = useParams();
  const { user } = useAuth();
  const [t, setT] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.get(`/events/gift/${token}`).then((r) => setT(r.data)).catch((e) => setErr(e?.response?.data?.detail || "Ticket not found"));
  }, [token]);

  if (err) return <div className="py-32 text-center" data-testid="gift-ticket-error"><div className="font-anton text-4xl uppercase">Ticket not found</div><Link to="/events" className="label-caps text-[#CCFF00] mt-6 inline-block">Browse events</Link></div>;
  if (!t) return <div className="py-32 text-center label-caps text-zinc-500">Loading ticket...</div>;

  const when = (() => { try { return new Date(t.event.start_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); } catch { return t.event.start_at; } })();
  const where = t.event.location?.city || t.event.location?.address || "TBA";
  const dead = t.refunded || t.event.cancelled;

  return (
    <div className="max-w-md mx-auto px-4 pt-10 pb-24" data-testid="gift-ticket-page">
      <div className="label-caps text-[#CCFF00] flex items-center gap-2"><Gift size={12} /> A ticket for you</div>
      <h1 className="font-anton text-4xl sm:text-5xl uppercase mt-3 leading-[0.9]">{t.event.title}</h1>
      <div className="text-sm text-zinc-400 mt-3">
        Hey {t.user_name} — <span className="text-white">{t.gifted_by_name || "a friend"}</span> bought this ticket for you.
      </div>
      {t.gift_message && <div className="mt-4 border-l-2 border-[#CCFF00] pl-4 text-zinc-300 italic text-sm" data-testid="gift-message">“{t.gift_message}”</div>}

      <div className="mt-8 border border-white/10 rounded-sm overflow-hidden bg-[#121214]">
        {t.event.cover_image && <img src={resolveImg(t.event.cover_image)} alt="" className="w-full h-40 object-cover" />}
        <div className="p-5 space-y-2 text-sm">
          <div className="flex items-center gap-2 text-zinc-300"><Calendar size={14} className="text-[#CCFF00]" /> {when}</div>
          <div className="flex items-center gap-2 text-zinc-300"><MapPin size={14} className="text-[#CCFF00]" /> {where}</div>
        </div>
        <div className="border-t border-dashed border-white/15 p-6 flex flex-col items-center">
          {dead ? (
            <div className="text-[#FF4D4D] label-caps" data-testid="gift-ticket-void">{t.event.cancelled ? "Event cancelled" : "Ticket refunded"}</div>
          ) : t.qr_image ? (
            <>
              <img src={t.qr_image} alt="Ticket QR" className="w-52 h-52 bg-white p-2 rounded-sm" data-testid="gift-qr-img" />
              <div className="label-caps text-zinc-500 mt-4 flex items-center gap-1"><QrCode size={11} /> Show this at the door</div>
              <WalletPassButton giftToken={token} className="mt-4 w-full !py-2" />
              {t.checked_in && <div className="text-[#CCFF00] text-xs mt-2 flex items-center gap-1"><CheckCircle2 size={12} /> Checked in</div>}
            </>
          ) : <div className="font-mono text-xs text-zinc-400 break-all">{t.qr_payload}</div>}
          <div className="text-[10px] text-zinc-600 mt-3 font-mono">ID {t.rsvp_id.slice(0, 8)}</div>
        </div>
      </div>

      {!user && !t.claimed && (
        <div className="mt-8 text-center text-xs text-zinc-500" data-testid="gift-claim-hint">
          Bookmark this page, or <Link to="/register" className="text-[#CCFF00] hover:underline">join Art Core</Link> with the email this was sent to and it'll appear in your Tickets.
        </div>
      )}
      <div className="mt-6 text-center"><Link to={`/events/${t.event.id}`} className="label-caps text-zinc-400 hover:text-white">View event →</Link></div>
    </div>
  );
}
