import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Hammer, ShieldCheck, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { api, thumbUrl, fileUrl } from "../../api";
import { useAuth } from "../../context/AuthContext";
import CommissionRequestModal from "../CommissionRequestModal";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export function FlipMyFurniture() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [artists, setArtists] = useState([]);
  const [target, setTarget] = useState(null);

  useEffect(() => { api.get("/commissions/flip/artists").then((r) => setArtists(r.data)).catch(() => {}); }, []);

  const request = (a) => {
    if (!user) { toast("Sign in to request a flip"); nav("/login"); return; }
    if (user.id === a.id) { toast("That's you!"); return; }
    setTarget(a);
  };

  return (
    <section className="mt-16 border border-[#34D399]/25 rounded-sm p-6 md:p-10 relative overflow-hidden" data-testid="flip-section">
      <div className="absolute -top-24 -right-24 w-72 h-72 bg-[#34D399] rounded-full opacity-[0.07] blur-3xl" />
      <div className="relative grid lg:grid-cols-[1fr_1.4fr] gap-8">
        <div>
          <div className="label-caps text-[#34D399] flex items-center gap-2"><Hammer size={12} /> Flip commissions</div>
          <h2 className="font-anton text-3xl md:text-5xl uppercase mt-3 leading-[0.9]">Got a tired piece?<br />Have it <span className="text-[#34D399]">flipped.</span></h2>
          <p className="text-zinc-400 text-sm md:text-base mt-4 max-w-md">Send your own chair, dresser or table to an Upcycle artist. You describe the vibe, they transform it — you keep the piece.</p>
          <ul className="mt-6 space-y-2 text-xs text-zinc-400">
            <li className="flex items-center gap-2"><ShieldCheck size={12} className="text-[#34D399]" /> Payment held in escrow — deposit to start, balance when you approve</li>
            <li className="flex items-center gap-2"><ShieldCheck size={12} className="text-[#34D399]" /> Progress photos along the way, dispute protection if it goes sideways</li>
            <li className="flex items-center gap-2"><ShieldCheck size={12} className="text-[#34D399]" /> Drop off, ship, or have the artist pick it up locally</li>
          </ul>
        </div>
        <div>
          {artists.length === 0 ? (
            <div className="text-zinc-500 label-caps py-12 text-center border border-dashed border-white/10 rounded-sm">No flip artists yet — be the first to list Upcycle work.</div>
          ) : (
            <div className="grid sm:grid-cols-2 gap-3" data-testid="flip-artists-grid">
              {artists.slice(0, 6).map((a) => (
                <div key={a.id} className="border border-white/8 rounded-sm overflow-hidden bg-[#121214] flex flex-col" data-testid={`flip-artist-${a.id}`}>
                  <div className="relative h-28 bg-white/[0.03]">
                    {a.sample && <img src={thumbUrl(a.sample, 480)} alt="" className="w-full h-full object-cover" />}
                    {a.before && <img src={thumbUrl(a.before, 240)} alt="" className="absolute bottom-2 left-2 w-12 h-12 object-cover rounded-sm border border-white/30 grayscale" />}
                  </div>
                  <div className="p-3 flex-1 flex flex-col">
                    <div className="flex items-center gap-2">
                      {a.avatar && <img src={resolveImg(a.avatar)} alt="" className="w-6 h-6 rounded-full object-cover" />}
                      <Link to={`/artist/${a.id}`} className="font-unbounded text-sm truncate hover:text-[#34D399]">{a.name}</Link>
                    </div>
                    <div className="text-[10px] text-zinc-500 mt-1 truncate">{a.pieces} flips listed{a.flips_done ? ` · ${a.flips_done} commissioned` : ""}{a.city ? ` · ${a.city}` : ""}</div>
                    <div className="flex flex-wrap gap-1 mt-2">{a.types.slice(0, 3).map((t) => <span key={t} className="label-caps text-[9px] px-1.5 py-0.5 border border-white/10 rounded-sm text-zinc-400 capitalize">{t}</span>)}</div>
                    <button data-testid={`flip-request-${a.id}`} onClick={() => request(a)} className="mt-3 label-caps text-[10px] text-[#34D399] hover:text-white flex items-center gap-1 transition-colors">Request a flip <ArrowRight size={11} /></button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      {target && <CommissionRequestModal artist={target} mode="flip" onClose={() => setTarget(null)} onSubmitted={() => nav("/commissions")} />}
    </section>
  );
}
