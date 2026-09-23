import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ArtCard, resolveImg } from "../components/ArtCard";
import { LiveAuctionRail, SignatureStudio } from "../components/HomeExtras";
import { StaffPicks } from "../components/home/StaffPicks";
import { ArrowUpRight, TrendingUp, Zap, Users, Gavel, Trophy } from "lucide-react";
import { KeepMoreStrip } from "../components/KeepMoreStrip";
import { useTranslation } from "react-i18next";

const HERO_BG = "https://images.unsplash.com/photo-1611063158871-7dd3ed4a2ac8?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA3MDB8MHwxfHNlYXJjaHwzfHxncmFmZml0aSUyMHN0cmVldCUyMGFydHxlbnwwfHx8fDE3ODYzOTAwMzl8MA&ixlib=rb-4.1.0&q=85";
const STUDIO_IMG = "https://images.unsplash.com/photo-1541753866388-0b3c701627d3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzR8MHwxfHNlYXJjaHwxfHxhcnRpc3QlMjBwYWludGluZyUyMHN0dWRpb3xlbnwwfHx8fDE3ODYzOTAwMzl8MA&ixlib=rb-4.1.0&q=85";
const GALLERY_IMG = "https://images.unsplash.com/photo-1617386069438-6b3a5f76f0bc?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzR8MHwxfHNlYXJjaHw0fHxtb2Rlcm4lMjBhcnQlMjBnYWxsZXJ5fGVufDB8fHx8MTc4NjM5MDAzOXww&ixlib=rb-4.1.0&q=85";

const CATEGORIES = [
  { name: "Paintings", color: "#CCFF00", medium: "Oil" },
  { name: "Digital", color: "#7C3AED", medium: "Digital" },
  { name: "Photography", color: "#FF4D4D", medium: "Photography" },
  { name: "Mixed Media", color: "#00E5FF", medium: "Mixed Media" },
  { name: "Watercolor", color: "#FFD700", medium: "Watercolor" },
  { name: "Acrylic", color: "#FF6EC7", medium: "Acrylic" },
];

const TESTIMONIALS = [
  { name: "Maya K.", role: "Painter · Berlin", text: "Art Core is where my work finally feels seen. Sold my first canvas in 3 days." },
  { name: "Devon R.", role: "Collector · NYC", text: "Behance meets Sotheby's — I've been waiting for this platform for a decade." },
  { name: "Rina T.", role: "Illustrator · Tokyo", text: "The commission system is going to change how I run my studio." },
];

export default function Home() {
  const { t } = useTranslation();
  const [feed, setFeed] = useState([]);
  const [artists, setArtists] = useState([]);
  const [stats, setStats] = useState({ artworks_live: 0, artists: 0, revenue: 0 });

  useEffect(() => {
    api.get("/feed?limit=12").then((r) => setFeed(r.data));
    api.get("/artists").then((r) => setArtists(r.data.slice(0, 6)));
    api.get("/admin/stats").then((r) => setStats(r.data)).catch(() => {
      // fallback for non-admin
      api.get("/artworks?limit=1").then(() => {});
    });
  }, []);

  return (
    <div data-testid="home-page">
      {/* HERO */}
      <section className="relative min-h-[92vh] overflow-hidden grain-overlay">
        <img src={HERO_BG} className="absolute inset-0 w-full h-full object-cover opacity-45" alt="" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#0A0A0C]/60 to-[#0A0A0C]" />
        <div className="relative max-w-[1600px] mx-auto px-6 md:px-12 pt-40 md:pt-56 pb-32">
          <div className="badge-lime mb-8" data-testid="hero-badge">{t("home.badge")}</div>
          <h1 className="font-anton text-7xl md:text-[10rem] leading-[0.82] uppercase tracking-tighter">
            {t("home.hero_1")}<br />
            <span className="text-[#CCFF00]">{t("home.hero_2")}</span> {t("home.hero_3")}<br />
            {t("home.hero_4")}
          </h1>
          <p className="text-lg md:text-xl text-zinc-300 mt-10 max-w-2xl leading-relaxed">
            {t("home.hero_sub")}
          </p>
          <div className="flex flex-wrap items-center gap-4 mt-12">
            <Link to="/explore" data-testid="hero-cta-explore" className="btn-lime">{t("home.explore_art")}</Link>
            <Link to="/register?role=artist" data-testid="hero-cta-sell" className="btn-ghost">{t("home.become_artist")}</Link>
            <Link to="/how-it-works" data-testid="hero-how-it-works" className="label-caps text-zinc-400 hover:text-[#CCFF00] transition-colors">How it works →</Link>
          </div>
          <div className="grid grid-cols-3 gap-8 mt-20 max-w-2xl">
            <Stat label={t("home.stat_artists")} value={stats.artists ?? 0} />
            <Stat label={t("home.stat_live_works")} value={stats.artworks_live ?? 0} />
            <Stat label={t("home.stat_categories")} value={CATEGORIES.length} />
          </div>
        </div>
      </section>

      {/* MARQUEE */}
      <section className="border-y border-white/8 py-5 overflow-hidden bg-[#121214]">
        <div className="whitespace-nowrap">
          <div className="marquee-scroll font-anton text-3xl md:text-5xl uppercase">
            {Array.from({ length: 6 }).map((_, i) => (
              <span key={i} className="mx-8">Original Art · Curated Chaos · <span className="text-[#CCFF00]">Art Core</span> · Since 2026 · </span>
            ))}
          </div>
        </div>
      </section>

      {/* LIVE AUCTIONS RAIL (real-time polling) */}
      <LiveAuctionRail />

      <StaffPicks />

      {/* CATEGORIES */}
      <section className="max-w-[1600px] mx-auto px-6 md:px-12 py-24">
        <SectionHeader kicker={t("home.browse")} title={t("home.popular_categories")} testid="section-categories" />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mt-12">
          {CATEGORIES.map((c) => (
            <Link key={c.name} to={`/marketplace?medium=${encodeURIComponent(c.medium)}`}
              data-testid={`category-${c.name.toLowerCase().replace(/\s/g, "-")}`}
              className="glass-card p-6 hover-lift-card group aspect-square flex flex-col justify-between rounded-sm">
              <div className="w-3 h-3 rounded-full" style={{ background: c.color, boxShadow: `0 0 16px ${c.color}` }} />
              <div>
                <div className="font-unbounded text-lg uppercase font-bold">{c.name}</div>
                <div className="label-caps mt-2 group-hover:text-[#CCFF00] transition-colors flex items-center gap-1">{t("home.enter")} <ArrowUpRight size={12} /></div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* TRENDING FEED */}
      <section className="max-w-[1600px] mx-auto px-6 md:px-12 py-24">
        <SectionHeader kicker={t("home.trending")} title={t("home.fresh")} testid="section-trending"
          right={<Link to="/explore" data-testid="trending-see-all" className="label-caps hover:text-[#CCFF00] flex items-center gap-1">{t("home.see_all")} <ArrowUpRight size={12} /></Link>}
        />
        {feed.length === 0 ? (
          <EmptySlot label="Artists — your work goes here." />
        ) : (
          <BentoGrid items={feed.slice(0, 8)} />
        )}
      </section>

      {/* FEATURED ARTISTS */}
      <section className="bg-[#121214] border-y border-white/5 py-24">
        <div className="max-w-[1600px] mx-auto px-6 md:px-12">
          <SectionHeader kicker={t("home.roster")} title={t("home.featured_artists")} testid="section-artists"
            right={<Link to="/artists" className="label-caps hover:text-[#CCFF00] flex items-center gap-1">{t("home.all_artists")} <ArrowUpRight size={12} /></Link>}
          />
          {artists.length === 0 ? <EmptySlot label={t("home.no_artists")} /> : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 mt-12">
              {artists.map((a) => (
                <Link key={a.id} to={`/artist/${a.id}`} data-testid={`featured-artist-${a.id}`}
                  className="text-center group">
                  <div className="avatar-ring w-24 h-24 mx-auto mb-4">
                    <div className="bg-[#0A0A0C] rounded-full w-full h-full flex items-center justify-center font-anton text-3xl uppercase">
                      {a.name?.[0] || "A"}
                    </div>
                  </div>
                  <div className="font-unbounded font-semibold text-sm group-hover:text-[#CCFF00] transition-colors truncate">{a.name}</div>
                  <div className="label-caps mt-1">{a.artwork_count} works</div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* LIVE FEATURES PROMO */}
      <section className="max-w-[1600px] mx-auto px-6 md:px-12 py-24">
        <div className="grid md:grid-cols-2 gap-8">
          <PromoBlock
            testid="promo-auctions"
            kicker={t("home.live_now")}
            title={t("home.live_auctions")}
            desc="Real-time bidding. Live countdowns. Watch pieces you love — win the ones you can't live without."
            to="/auctions"
            icon={<Gavel />}
            accent="#7C3AED"
            bg={GALLERY_IMG}
          />
          <PromoBlock
            testid="promo-commissions"
            kicker={t("home.live_now")}
            title={t("home.commissions")}
            desc="Request custom work. Set a budget, a deadline, a vibe. Chat with artists as they build it."
            to="/commissions"
            icon={<Zap />}
            accent="#CCFF00"
            bg={STUDIO_IMG}
          />
        </div>
      </section>

      {/* SIGNATURE STUDIO */}
      <SignatureStudio />

      {/* TESTIMONIALS */}
      <section className="max-w-[1600px] mx-auto px-6 md:px-12 py-24">
        <SectionHeader kicker={t("home.word")} title={t("home.what_people_say")} testid="section-testimonials" />
        <div className="grid md:grid-cols-3 gap-6 mt-12">
          {TESTIMONIALS.map((t, i) => (
            <div key={i} data-testid={`testimonial-${i}`} className="glass-card p-8 rounded-sm">
              <div className="text-[#CCFF00] font-anton text-6xl leading-none">"</div>
              <p className="text-zinc-200 leading-relaxed mt-2">{t.text}</p>
              <div className="mt-6 border-t border-white/8 pt-4">
                <div className="font-unbounded font-semibold text-sm">{t.name}</div>
                <div className="label-caps mt-1">{t.role}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <KeepMoreStrip />

      {/* CTA */}
      <section className="max-w-[1600px] mx-auto px-6 md:px-12 py-32">
        <div className="glass-card p-12 md:p-24 relative overflow-hidden rounded-sm">
          <div className="absolute -top-40 -right-40 w-96 h-96 bg-[#CCFF00] rounded-full opacity-10 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-[#7C3AED] rounded-full opacity-15 blur-3xl" />
          <div className="relative">
            <div className="label-caps text-[#CCFF00]">{t("home.for_creators")}</div>
            <h2 className="font-anton text-5xl md:text-8xl uppercase mt-4 leading-[0.9]">{t("home.bring_1")} <span className="text-[#CCFF00]">{t("home.bring_2")}</span><br />{t("home.bring_3")}</h2>
            <p className="text-zinc-300 mt-8 max-w-2xl">{t("home.cta_sub")}</p>
            <div className="flex flex-wrap gap-4 mt-10">
              <Link to="/register?role=artist" data-testid="cta-signup" className="btn-lime">{t("home.apply_to_sell")}</Link>
              <Link to="/explore" data-testid="cta-explore" className="btn-ghost">{t("home.browse_first")}</Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function SectionHeader({ kicker, title, right, testid }) {
  return (
    <div className="flex items-end justify-between flex-wrap gap-4" data-testid={testid}>
      <div>
        <div className="label-caps text-[#CCFF00]">{kicker}</div>
        <h2 className="font-anton text-4xl md:text-6xl uppercase mt-3 tracking-tight">{title}</h2>
      </div>
      {right}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="font-anton text-5xl md:text-7xl text-[#CCFF00]">{value}</div>
      <div className="label-caps mt-2">{label}</div>
    </div>
  );
}

function EmptySlot({ label }) {
  return <div className="border border-dashed border-white/10 py-24 text-center label-caps text-zinc-500 mt-12 rounded-sm">{label}</div>;
}

function BentoGrid({ items }) {
  // 8 items → 1 big, 2 wide, 5 regular arranged bento-style
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 auto-rows-[240px] md:auto-rows-[280px] gap-4 mt-12">
      {items.map((art, i) => {
        const cls =
          i === 0 ? "col-span-2 row-span-2" :
          i === 3 ? "md:col-span-2" :
          i === 6 ? "md:col-span-2" : "";
        return (
          <div key={art.id} className={cls}>
            <div className="h-full">
              <ArtCardBig art={art} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ArtCardBig({ art }) {
  return (
    <Link to={`/artwork/${art.id}`} data-testid={`bento-${art.id}`}
      className="block h-full relative overflow-hidden border border-white/8 hover-lift-card bg-[#121214] group rounded-sm">
      <img src={resolveImg(art.images?.[0])} alt={art.title} loading="lazy"
        className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent" />
      <div className="absolute bottom-0 left-0 right-0 p-5">
        <div className="font-unbounded font-semibold text-lg">{art.title}</div>
        <div className="flex items-center justify-between mt-1">
          <div className="text-xs text-zinc-300">{art.artist?.name}</div>
          <div className="text-sm text-[#CCFF00] font-bold">${Number(art.price).toLocaleString()}</div>
        </div>
      </div>
      {art.aotw && <div className="absolute top-3 left-3 badge-lime">Featured ★</div>}
    </Link>
  );
}

function PromoBlock({ testid, kicker, title, desc, to, icon, accent, bg }) {
  return (
    <Link to={to} data-testid={testid} className="relative overflow-hidden group border border-white/8 hover:border-[color:var(--a)] rounded-sm block min-h-[340px]"
      style={{ "--a": accent }}>
      <img src={bg} className="absolute inset-0 w-full h-full object-cover opacity-30 group-hover:opacity-40 transition-opacity" alt="" />
      <div className="absolute inset-0 bg-gradient-to-br from-[#0A0A0C]/95 via-[#0A0A0C]/70 to-transparent" />
      <div className="relative p-10 h-full flex flex-col justify-between">
        <div>
          <div className="label-caps" style={{ color: accent }}>{kicker}</div>
          <h3 className="font-anton text-5xl md:text-6xl uppercase mt-4 leading-none">{title}</h3>
        </div>
        <div>
          <p className="text-zinc-300 leading-relaxed max-w-md">{desc}</p>
          <div className="flex items-center gap-2 mt-6 label-caps" style={{ color: accent }}>
            {icon} <span>Get notified</span> <ArrowUpRight size={14} />
          </div>
        </div>
      </div>
    </Link>
  );
}
