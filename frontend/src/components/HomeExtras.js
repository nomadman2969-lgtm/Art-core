import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "../api";
import { Gavel, Clock } from "lucide-react";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

/**
 * Live auction rail that polls /api/auctions?status=live every 6s and flashes
 * a subtle pulse when the current_bid or bid_count changes on any card.
 */
export function LiveAuctionRail() {
  const [auctions, setAuctions] = useState([]);
  const [pulses, setPulses] = useState({}); // id -> timestamp when it should pulse

  useEffect(() => {
    let prev = new Map();
    const tick = async () => {
      try {
        const r = await api.get("/auctions?status=live&limit=8");
        const changed = {};
        r.data.forEach((a) => {
          const p = prev.get(a.id);
          if (p && (p.current_bid !== a.current_bid || p.bid_count !== a.bid_count)) {
            changed[a.id] = Date.now();
          }
        });
        setAuctions(r.data);
        prev = new Map(r.data.map((a) => [a.id, { current_bid: a.current_bid, bid_count: a.bid_count }]));
        if (Object.keys(changed).length) {
          setPulses((old) => ({ ...old, ...changed }));
          setTimeout(() => setPulses({}), 2000);
        }
      } catch {}
    };
    tick();
    const t = setInterval(tick, 6000);
    return () => clearInterval(t);
  }, []);

  if (auctions.length === 0) return null;
  return (
    <section data-testid="home-live-auctions" className="max-w-[1600px] mx-auto px-6 md:px-12 py-16">
      <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
        <div>
          <div className="label-caps text-[#7C3AED] flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#FF4D4D] animate-pulse" /> Live Auctions
          </div>
          <h2 className="font-anton text-4xl md:text-6xl uppercase mt-3">Bidding Now</h2>
        </div>
        <Link to="/auctions" className="label-caps hover:text-[#CCFF00]">All auctions →</Link>
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        {auctions.slice(0, 4).map((a) => (
          <LiveAuctionMini key={a.id} a={a} pulse={pulses[a.id]} />
        ))}
      </div>
    </section>
  );
}

function LiveAuctionMini({ a, pulse }) {
  const [rem, setRem] = useState(Math.max(0, new Date(a.end_at) - new Date()));
  useEffect(() => {
    const t = setInterval(() => setRem(Math.max(0, new Date(a.end_at) - new Date())), 1000);
    return () => clearInterval(t);
  }, [a.end_at]);
  const sec = Math.floor(rem / 1000);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return (
    <Link to={`/auctions/${a.id}`} data-testid={`home-auction-${a.id}`}
      className={`block border hover-lift-card bg-[#121214] rounded-sm relative overflow-hidden transition-all duration-500 ${pulse ? "border-[#CCFF00] shadow-[0_0_32px_rgba(204,255,0,0.4)]" : "border-white/8"}`}>
      <div className="aspect-square overflow-hidden bg-black">
        <img src={resolveImg(a.artwork?.images?.[0])} alt="" className="w-full h-full object-cover" />
      </div>
      <div className="absolute top-2 left-2 badge-violet"><Gavel size={9} className="inline mr-1" /> {a.bid_count} bids</div>
      {pulse && <div className="absolute top-2 right-2 badge-lime animate-pulse">New Bid</div>}
      <div className="p-4">
        <div className="font-unbounded font-semibold truncate text-sm">{a.artwork?.title}</div>
        <div className="flex items-baseline justify-between mt-2">
          <div className="font-anton text-xl text-[#CCFF00]">${Number(a.current_bid || a.start_price).toLocaleString()}</div>
          <div className="label-caps text-xs flex items-center gap-1"><Clock size={9} /> {String(h).padStart(2, "0")}:{String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}</div>
        </div>
      </div>
    </Link>
  );
}

/**
 * Featured "signature" studio — pulls #1 ranked artist, shows their studio card with
 * their theme background, top artwork, and rank badge.
 */
export function SignatureStudio() {
  const [artist, setArtist] = useState(null);
  const [studio, setStudio] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const lb = (await api.get("/rankings/leaderboard?limit=1")).data;
        if (!lb.length) return;
        const top = lb[0];
        const s = (await api.get(`/studio/${top.id}`)).data;
        setArtist({ ...top });
        setStudio(s);
      } catch {}
    })();
  }, []);
  if (!artist || !studio) return null;
  const theme = studio.config.theme;
  const accent = studio.config.accent_color || "#CCFF00";
  const bg = studio.config.background?.type === "image" && studio.config.background?.value;
  const topArt = studio.artworks?.featured?.[0] || studio.artworks?.available?.[0] || studio.artworks?.all?.[0];
  return (
    <section data-testid="signature-studio" className="max-w-[1600px] mx-auto px-6 md:px-12 py-24">
      <div className="mb-8">
        <div className="label-caps" style={{ color: accent }}>Signature Studio · {artist.tier}</div>
        <h2 className="font-anton text-4xl md:text-6xl uppercase mt-3">The Top-Ranked Room</h2>
      </div>
      <Link to={`/artist/${artist.id}`} data-testid="signature-link"
        className="block relative overflow-hidden border border-white/8 hover-lift-card rounded-sm min-h-[420px] group">
        {bg ? (
          <img src={bg} className="absolute inset-0 w-full h-full object-cover opacity-45" alt="" />
        ) : topArt ? (
          <img src={resolveImg(topArt.images?.[0])} className="absolute inset-0 w-full h-full object-cover opacity-40" alt="" />
        ) : (
          <div className="absolute inset-0 bg-gradient-to-br from-[#121214] to-[#1A1A1E]" />
        )}
        <div className="absolute inset-0 bg-gradient-to-r from-[#0A0A0C]/95 via-[#0A0A0C]/80 to-transparent" />
        <div className="relative p-8 md:p-16 grid md:grid-cols-2 gap-10 items-center min-h-[420px]">
          <div>
            <div className="label-caps mb-4" style={{ color: accent }}>#{artist.position || 1} · {artist.tier} · {artist.score} pts</div>
            <h3 className="font-anton text-5xl md:text-7xl uppercase leading-[0.9]">{artist.name}</h3>
            <p className="text-zinc-300 mt-6 max-w-md leading-relaxed line-clamp-3">{studio.artist.bio || "Independent artist featured this week on Art Core."}</p>
            <div className="flex flex-wrap gap-6 mt-8">
              <div><div className="font-anton text-3xl" style={{ color: accent }}>{artist.breakdown.sales}</div><div className="label-caps mt-1">Sales</div></div>
              <div><div className="font-anton text-3xl" style={{ color: accent }}>{artist.breakdown.followers}</div><div className="label-caps mt-1">Followers</div></div>
              <div><div className="font-anton text-3xl" style={{ color: accent }}>{artist.breakdown.artworks}</div><div className="label-caps mt-1">Works</div></div>
            </div>
            <div className="btn-lime mt-10 w-fit">Enter Studio →</div>
          </div>
          {topArt && (
            <div className="hidden md:block">
              <img src={resolveImg(topArt.images?.[0])} className="w-full aspect-[4/5] object-cover border-4 border-white/10 shadow-2xl group-hover:scale-[1.02] transition-transform duration-500" alt="" />
              <div className="mt-3 label-caps">Featured piece · {topArt.title}</div>
            </div>
          )}
        </div>
      </Link>
    </section>
  );
}
