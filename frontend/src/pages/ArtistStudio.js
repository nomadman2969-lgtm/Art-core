import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, fileUrl } from "../api";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { toast } from "sonner";
import { RankBadge } from "./Rankings";
import { BadgeRow } from "../components/BadgeRow";
import { ReportButton } from "../components/ReportButton";
import {
  UserPlus, UserCheck, MessageCircle, Palette, Share2, Eye,
  Gavel, Clock, Heart, MessageSquare, Pin, MapPin, Instagram, Twitter, Globe,
  Megaphone, ArrowRight, ChevronLeft, ChevronRight,
} from "lucide-react";
import CommissionRequestModal from "../components/CommissionRequestModal";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

// ---------- Immersive Studio (visitor + owner) ----------
export function ArtistStudioPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const previewMode = searchParams.get("preview") === "1";
  const nav = useNavigate();
  const { user } = useAuth();
  const [studio, setStudio] = useState(null);
  const [rank, setRank] = useState(null);
  const [social, setSocial] = useState(null);
  const [commissionOpen, setCommissionOpen] = useState(false);

  const load = () => {
    const url = previewMode ? `/studio/${id}?preview=true` : `/studio/${id}`;
    api.get(url).then((r) => setStudio(r.data)).catch(() => nav("/artists"));
    api.get(`/rankings/${id}`).then((r) => setRank(r.data)).catch(() => {});
    api.get(`/users/${id}/social`).then((r) => setSocial(r.data)).catch(() => {});
  };
  useEffect(() => {
    load();
    const t = setInterval(() => {
      const url = previewMode ? `/studio/${id}?preview=true` : `/studio/${id}`;
      api.get(url).then((r) => setStudio((old) => old ? { ...old, auctions: r.data.auctions, posts: r.data.posts } : r.data)).catch(() => {});
    }, 8000);
    return () => clearInterval(t);
  }, [id, previewMode]);

  if (!studio) return <div className="py-32 text-center label-caps text-zinc-500">Entering studio...</div>;
  const { artist, config, artworks, auctions, posts } = studio;
  const theme = studio.theme || config.theme || "urban_graffiti";
  const accent = config.accent_color;
  const isOwner = user?.id === artist.id;

  const toggleFollow = async () => {
    if (!user) { toast("Sign in to follow"); return; }
    try {
      if (social?.is_following) await api.delete(`/users/${id}/follow`);
      else await api.post(`/users/${id}/follow`);
      load();
    } catch { toast.error("Try again"); }
  };
  const share = () => {
    const u = `${process.env.REACT_APP_BACKEND_URL}/api/share/studio/${artist.id}`;
    if (navigator.share) navigator.share({ title: `${artist.name}'s Studio · Art Core`, url: u }).catch(() => {});
    else { navigator.clipboard.writeText(u); toast.success("Link copied"); }
  };

  return (
    <StudioThemeShell theme={config.theme} accent={accent} config={config}>
      {config.is_preview && (
        <div data-testid="preview-banner" className="sticky top-0 z-40 bg-[#F5A623] text-black py-2 px-6 text-center font-anton uppercase text-sm">
          Preview mode · showing your unpublished draft · <Link to="/studio" className="underline">Back to editor</Link>
        </div>
      )}
      {/* HEADER */}
      <div className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-12" data-testid="studio-header">
        <div className="flex flex-wrap gap-8 items-start">
          <div className="avatar-ring w-32 h-32 flex-shrink-0">
            <div className="bg-[#0A0A0C] rounded-full w-full h-full flex items-center justify-center font-anton text-5xl uppercase">
              {artist.name?.[0]}
            </div>
          </div>
          <div className="flex-1 min-w-[280px]">
            <div className="label-caps mb-2" style={{ color: "var(--accent)" }}>The Studio of</div>
            <h1 className="font-anton text-6xl md:text-8xl uppercase leading-[0.9] tracking-tight">{artist.name}</h1>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              {config.artist_story?.location && <span className="label-caps flex items-center gap-1"><MapPin size={12} /> {config.artist_story.location}</span>}
              {config.artist_story?.style && <span className="label-caps">· {config.artist_story.style}</span>}
              {rank && <RankBadge tier={rank.tier} color={rank.tier_color} />}
            </div>
            <BadgeRow userId={artist.id} />
            <div className="flex flex-wrap gap-6 mt-6">
              <MetricInline label="Followers" value={social?.followers ?? 0} />
              <MetricInline label="Following" value={social?.following ?? 0} />
              <MetricInline label="Visits" value={config.visits ?? 0} />
              <MetricInline label="Works" value={artworks.all.length} />
              {rank && <MetricInline label="Rank" value={`#${rank.position || "—"}`} />}
            </div>
            <div className="flex flex-wrap gap-3 mt-6">
              {!isOwner && user && (
                <button data-testid="studio-follow" onClick={toggleFollow}
                  className={social?.is_following ? "btn-ghost" : "btn-lime"}>
                  {social?.is_following ? <><UserCheck size={14} className="mr-2" />Following</> : <><UserPlus size={14} className="mr-2" />Follow</>}
                </button>
              )}
              {!isOwner && user && (
                <button data-testid="studio-message" onClick={() => nav(`/messages/${artist.id}`)} className="btn-ghost">
                  <MessageCircle size={14} className="mr-2" /> Message
                </button>
              )}
              {!isOwner && (
                <button data-testid="studio-commission" onClick={() => {
                  if (!user) { nav("/login"); return; }
                  setCommissionOpen(true);
                }} className="btn-violet">
                  <Palette size={14} className="mr-2" /> Commission
                </button>
              )}
              <button data-testid="studio-share" onClick={share} className="btn-ghost"><Share2 size={14} className="mr-2" /> Share</button>
              <ReportButton targetType="user" targetId={artist.id} ownerId={artist.id} />
              {isOwner && (
                <Link to="/studio" data-testid="studio-edit" className="btn-lime">Edit Studio</Link>
              )}
            </div>
          </div>
        </div>
        {artist.bio && (
          <p className="text-lg text-zinc-200 leading-relaxed max-w-3xl mt-8 whitespace-pre-wrap">{artist.bio}</p>
        )}
      </div>

      {/* SECTIONS */}
      <div className="max-w-[1600px] mx-auto px-6 md:px-12 space-y-24 pb-32">
        {(config.sections || [])
          .filter((s) => s.visible !== false)
          .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
          .map((section) => (
            <StudioSection key={section.id} section={section} studio={studio} isOwner={isOwner} onRefresh={load} />
          ))}
      </div>

      {commissionOpen && (
        <CommissionRequestModal
          artist={artist}
          allowFlip={(artworks?.all || []).some((a) => a.section === "upcycle")}
          onClose={() => setCommissionOpen(false)}
          onSubmitted={() => setCommissionOpen(false)}
        />
      )}
    </StudioThemeShell>
  );
}

// ---------- Section renderer ----------
function StudioSection({ section, studio, isOwner, onRefresh }) {
  const { artworks, auctions, posts, config, artist } = studio;
  const kind = section.kind;

  const title = <SectionTitle title={section.title} testid={`section-${section.id}`} />;
  const layout = section.layout || "grid";

  if (kind === "featured_works") {
    const items = artworks.featured.length ? artworks.featured : artworks.available.slice(0, 6);
    if (!items.length) return null;
    return <div data-testid={`sec-${section.id}`}>{title}<ArtworkWall items={items} layout={layout} /></div>;
  }
  if (kind === "available_now") {
    if (!artworks.available.length) return null;
    return <div data-testid={`sec-${section.id}`}>{title}<ArtworkWall items={artworks.available} layout={layout} /></div>;
  }
  if (kind === "sold_works") {
    if (!artworks.sold.length) return null;
    return <div data-testid={`sec-${section.id}`}>{title}<ArtworkWall items={artworks.sold} layout={layout} /></div>;
  }
  if (kind === "upcoming_auctions") {
    if (!auctions.length) return null;
    return <div data-testid={`sec-${section.id}`}>{title}<AuctionWall items={auctions} /></div>;
  }
  if (kind === "feed") {
    return <div data-testid={`sec-${section.id}`}>{title}<StudioFeed posts={posts} isOwner={isOwner} onRefresh={onRefresh} /></div>;
  }
  if (kind === "story") {
    return <div data-testid={`sec-${section.id}`}>{title}<StoryBlock story={config.artist_story} artist={artist} /></div>;
  }
  if (kind === "commission") {
    if (config.commission_open === false) {
      return (
        <div data-testid={`sec-${section.id}`}>
          {title}
          <div className="glass-card p-8 rounded-sm">
            <div className="label-caps text-zinc-500">Commissions currently closed</div>
            <div className="mt-2 text-zinc-300">{artist?.name || "This artist"} is not accepting new commissions right now. Check back soon.</div>
          </div>
        </div>
      );
    }
    return (
      <div id="commission" data-testid={`sec-${section.id}`}>
        {title}
        <CommissionBlock artistId={artist.id} artist={artist} blurb={config.commission_blurb} isOwner={isOwner} />
        <CompletedCommissionsRail artistId={artist.id} />
      </div>
    );
  }
  if (kind === "announcement") {
    return <div data-testid={`sec-${section.id}`}>{title}<AnnouncementBlock section={section} /></div>;
  }
  if (kind === "text_block") {
    return (
      <div data-testid={`sec-${section.id}`}>
        {title}
        <div className="glass-card p-8 rounded-sm max-w-3xl text-zinc-100 leading-relaxed whitespace-pre-wrap">{section.body || ""}</div>
      </div>
    );
  }
  if (kind === "button_cta") {
    return <div data-testid={`sec-${section.id}`}>{title}<ButtonCta section={section} /></div>;
  }
  if (kind === "image_block") {
    return (
      <div data-testid={`sec-${section.id}`}>
        {title}
        <div className="glass-card p-4 rounded-sm max-w-4xl">
          {section.image && <img src={resolveImg(section.image)} className="w-full rounded-sm" alt={section.caption || ""} loading="lazy" />}
          {section.caption && <div className="label-caps mt-3" style={{ color: "var(--accent)" }}>{section.caption}</div>}
          {section.body && <div className="text-zinc-300 mt-2 whitespace-pre-wrap">{section.body}</div>}
        </div>
      </div>
    );
  }
  if (kind === "custom") {
    return <div data-testid={`sec-${section.id}`}>{title}<div className="text-zinc-300 leading-relaxed max-w-3xl whitespace-pre-wrap">{section.body || "Custom section."}</div></div>;
  }
  return null;
}

function AnnouncementBlock({ section }) {
  const variant = section.variant || "info";
  const colorMap = {
    info: { bg: "rgba(124,58,237,0.15)", border: "#7C3AED", accent: "#7C3AED" },
    success: { bg: "rgba(204,255,0,0.12)", border: "#CCFF00", accent: "#CCFF00" },
    warning: { bg: "rgba(245,166,35,0.15)", border: "#F5A623", accent: "#F5A623" },
  };
  const c = colorMap[variant] || colorMap.info;
  return (
    <div className="p-6 rounded-sm border-l-4 max-w-3xl" style={{ background: c.bg, borderColor: c.border }}>
      <div className="flex items-start gap-4">
        <Megaphone size={22} color={c.accent} className="flex-shrink-0 mt-1" />
        <div className="text-zinc-100 leading-relaxed whitespace-pre-wrap">{section.body || ""}</div>
      </div>
    </div>
  );
}

function ButtonCta({ section }) {
  const link = section.button_link || "#";
  const isInternal = link.startsWith("#") || link.startsWith("/");
  const Wrapper = ({ children }) => isInternal
    ? <a href={link} className="inline-flex items-center btn-lime">{children}</a>
    : <a href={link} target="_blank" rel="noreferrer" className="inline-flex items-center btn-lime">{children}</a>;
  return (
    <div className="glass-card p-8 rounded-sm max-w-3xl">
      {section.body && <p className="text-zinc-200 mb-6 leading-relaxed">{section.body}</p>}
      <Wrapper>
        {section.button_text || "Click"} <ArrowRight size={14} className="ml-2" />
      </Wrapper>
    </div>
  );
}

function SectionTitle({ title, testid }) {
  return (
    <div className="mb-10 flex items-baseline gap-4" data-testid={testid}>
      <div className="w-2 h-10" style={{ background: "var(--accent)" }} />
      <h2 className="font-anton text-4xl md:text-6xl uppercase">{title}</h2>
    </div>
  );
}

function MetricInline({ label, value }) {
  return (
    <div>
      <div className="font-anton text-3xl" style={{ color: "var(--accent)" }}>{value}</div>
      <div className="label-caps mt-1">{label}</div>
    </div>
  );
}

// ---------- Artwork wall — layouts: grid | masonry | salon | showcase | carousel ----------
function ArtworkWall({ items, layout = "grid" }) {
  if (layout === "showcase") return <ShowcaseWall items={items} />;
  if (layout === "carousel") return <CarouselWall items={items} />;
  if (layout === "masonry") return <MasonryWall items={items} />;
  if (layout === "salon") return <SalonWall items={items} />;
  return <GridWall items={items} />;
}

function ArtCardTile({ a, aspectClass = "aspect-square" }) {
  return (
    <Link to={`/artwork/${a.id}`} data-testid={`wall-art-${a.id}`}
      className="block relative group overflow-hidden hover-lift-card border border-white/8 bg-black rounded-sm">
      <img src={resolveImg(a.images?.[0])} className={`w-full ${aspectClass} object-cover transition-transform duration-700 group-hover:scale-105`} alt={a.title} loading="lazy" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-transparent opacity-70 group-hover:opacity-100 transition-opacity" />
      <div className="absolute top-3 left-3 flex flex-col gap-2">
        {a.status === "sold" && <div className="badge-coral">Sold</div>}
        {a.status === "live" && <div className="badge-lime">Available</div>}
        {a.aotw && <div className="badge-violet">Featured ★</div>}
      </div>
      <div className="absolute bottom-0 left-0 right-0 p-4">
        <div className="font-unbounded font-semibold text-white text-lg leading-tight">{a.title}</div>
        <div className="flex items-baseline justify-between mt-1">
          <div className="label-caps">{a.medium}</div>
          <div className="font-anton text-xl" style={{ color: "var(--accent)" }}>${Number(a.price).toLocaleString()}</div>
        </div>
      </div>
    </Link>
  );
}

function GridWall({ items }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {items.map((a, i) => (
        <div key={a.id} className={i % 7 === 0 ? "col-span-2 row-span-2" : ""}>
          <ArtCardTile a={a} />
        </div>
      ))}
    </div>
  );
}

function MasonryWall({ items }) {
  // CSS columns for true masonry
  return (
    <div className="columns-2 md:columns-3 lg:columns-4 gap-4 space-y-4">
      {items.map((a) => (
        <div key={a.id} className="break-inside-avoid">
          <Link to={`/artwork/${a.id}`} data-testid={`wall-art-${a.id}`}
            className="block relative group overflow-hidden hover-lift-card border border-white/8 bg-black rounded-sm">
            <img src={resolveImg(a.images?.[0])} className="w-full object-cover transition-transform duration-700 group-hover:scale-105" alt={a.title} loading="lazy" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-transparent opacity-70 group-hover:opacity-100 transition-opacity" />
            <div className="absolute top-3 left-3">
              {a.status === "sold" && <div className="badge-coral">Sold</div>}
              {a.status === "live" && <div className="badge-lime">Available</div>}
            </div>
            <div className="absolute bottom-0 left-0 right-0 p-3">
              <div className="font-unbounded font-semibold text-white text-sm">{a.title}</div>
              <div className="font-anton text-lg" style={{ color: "var(--accent)" }}>${Number(a.price).toLocaleString()}</div>
            </div>
          </Link>
        </div>
      ))}
    </div>
  );
}

function SalonWall({ items }) {
  // Salon-style: pieces of varied sizes on a "wall"
  const sizes = ["col-span-2 row-span-2", "col-span-1 row-span-1", "col-span-1 row-span-1", "col-span-1 row-span-2", "col-span-2 row-span-1", "col-span-1 row-span-1"];
  return (
    <div className="relative p-8 border border-white/10 rounded-sm bg-gradient-to-b from-white/[0.02] to-transparent">
      {/* wall trim */}
      <div className="absolute inset-x-0 top-0 h-px bg-white/20" />
      <div className="absolute inset-x-0 bottom-0 h-px bg-white/10" />
      <div className="grid grid-cols-4 auto-rows-[130px] md:auto-rows-[180px] gap-4">
        {items.map((a, i) => (
          <div key={a.id} className={sizes[i % sizes.length]}>
            <ArtCardTile a={a} aspectClass="h-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

function ShowcaseWall({ items }) {
  const [idx, setIdx] = useState(0);
  const hero = items[idx];
  if (!hero) return null;
  return (
    <div>
      <Link to={`/artwork/${hero.id}`} data-testid={`showcase-${hero.id}`} className="block relative group overflow-hidden rounded-sm border border-white/8 bg-black">
        <img src={resolveImg(hero.images?.[0])} className="w-full max-h-[75vh] object-contain bg-black" alt={hero.title} />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent pointer-events-none" />
        <div className="absolute bottom-0 left-0 right-0 p-6">
          <div className="font-anton text-3xl md:text-5xl uppercase">{hero.title}</div>
          <div className="flex items-baseline gap-4 mt-2">
            <div className="label-caps">{hero.medium}</div>
            <div className="font-anton text-2xl" style={{ color: "var(--accent)" }}>${Number(hero.price).toLocaleString()}</div>
          </div>
        </div>
      </Link>
      {items.length > 1 && (
        <div className="flex gap-2 mt-4 overflow-x-auto pb-2">
          {items.map((a, i) => (
            <button key={a.id} onClick={() => setIdx(i)}
              className={`w-16 h-16 flex-shrink-0 border-2 rounded-sm ${i === idx ? "border-[color:var(--accent)]" : "border-white/10"}`}>
              <img src={resolveImg(a.images?.[0])} className="w-full h-full object-cover" alt="" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function CarouselWall({ items }) {
  const [pos, setPos] = useState(0);
  const perPage = 3;
  const total = items.length;
  const canPrev = pos > 0;
  const canNext = pos + perPage < total;
  return (
    <div className="relative">
      <div className="flex gap-4 overflow-hidden">
        {items.slice(pos, pos + perPage).map((a) => (
          <div key={a.id} className="flex-1 min-w-0">
            <ArtCardTile a={a} />
          </div>
        ))}
      </div>
      <div className="flex justify-between mt-4">
        <button disabled={!canPrev} onClick={() => setPos(Math.max(0, pos - 1))} className="btn-ghost !py-2 disabled:opacity-30"><ChevronLeft size={16} /></button>
        <div className="label-caps">{pos + 1}–{Math.min(pos + perPage, total)} of {total}</div>
        <button disabled={!canNext} onClick={() => setPos(Math.min(total - perPage, pos + 1))} className="btn-ghost !py-2 disabled:opacity-30"><ChevronRight size={16} /></button>
      </div>
    </div>
  );
}

// ---------- Live auction rail ----------
function AuctionWall({ items }) {
  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((au) => <AuctionCardMini key={au.id} au={au} />)}
    </div>
  );
}
function AuctionCardMini({ au }) {
  const [rem, setRem] = useState(Math.max(0, new Date(au.end_at) - new Date()));
  useEffect(() => {
    const t = setInterval(() => setRem(Math.max(0, new Date(au.end_at) - new Date())), 1000);
    return () => clearInterval(t);
  }, [au.end_at]);
  const sec = Math.floor(rem / 1000);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return (
    <Link to={`/auctions/${au.id}`} data-testid={`studio-auction-${au.id}`}
      className="block border border-white/8 hover-lift-card bg-[#121214] rounded-sm">
      <div className="aspect-video overflow-hidden bg-black relative">
        <img src={resolveImg(au.artwork?.images?.[0])} className="w-full h-full object-cover" alt="" />
        <div className="absolute top-3 left-3 badge-violet"><Gavel size={10} className="inline mr-1" /> Live · {au.bid_count} bids</div>
      </div>
      <div className="p-4">
        <div className="font-unbounded font-semibold text-lg">{au.artwork?.title}</div>
        <div className="flex items-baseline justify-between mt-3">
          <div>
            <div className="label-caps">Current bid</div>
            <div className="font-anton text-2xl" style={{ color: "var(--accent)" }}>${Number(au.current_bid || au.start_price).toLocaleString()}</div>
          </div>
          <div className="text-right">
            <div className="label-caps flex items-center gap-1 justify-end"><Clock size={10} /> Ends in</div>
            <div className="font-anton text-lg">{String(h).padStart(2, "0")}:{String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}</div>
          </div>
        </div>
      </div>
    </Link>
  );
}

// ---------- Feed ----------
function StudioFeed({ posts, isOwner, onRefresh }) {
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setPosting(true);
    try {
      await api.post("/posts", { text, kind: "update" });
      setText(""); toast.success("Posted"); onRefresh();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    setPosting(false);
  };
  const del = async (pid) => {
    if (!confirm("Delete post?")) return;
    await api.delete(`/posts/${pid}`); onRefresh();
  };
  const pinToggle = async (p) => {
    await api.patch(`/posts/${p.id}/pin`, { pinned: !p.pinned }); onRefresh();
  };
  return (
    <div>
      {isOwner && (
        <form onSubmit={submit} className="glass-card p-4 rounded-sm mb-8">
          <textarea data-testid="post-input" value={text} onChange={(e) => setText(e.target.value)} rows={3}
            placeholder="Share something with your collectors..."
            className="w-full bg-transparent outline-none resize-none" />
          <div className="flex justify-end mt-2">
            <button data-testid="post-submit" disabled={posting || !text.trim()} className="btn-lime !py-2 !text-xs">Post</button>
          </div>
        </form>
      )}
      {posts.length === 0 ? (
        <div className="border border-dashed border-white/10 py-16 text-center label-caps text-zinc-500 rounded-sm">
          {isOwner ? "No posts yet — share something." : "No posts yet."}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {posts.map((p) => (
            <div key={p.id} data-testid={`post-${p.id}`} className="glass-card p-6 rounded-sm">
              <div className="flex items-center justify-between mb-3">
                <div className="label-caps flex items-center gap-2">
                  {p.pinned && <Pin size={12} style={{ color: "var(--accent)" }} />} {p.kind} · {new Date(p.created_at).toLocaleDateString()}
                </div>
                {isOwner && (
                  <div className="flex gap-2">
                    <button onClick={() => pinToggle(p)} className="label-caps hover:text-[#CCFF00]">{p.pinned ? "Unpin" : "Pin"}</button>
                    <button onClick={() => del(p.id)} className="label-caps hover:text-[#FF4D4D]">Delete</button>
                  </div>
                )}
              </div>
              <div className="text-zinc-100 whitespace-pre-wrap leading-relaxed">{p.text}</div>
              {p.image && <img src={resolveImg(p.image)} className="mt-4 w-full rounded-sm" alt="" />}
              <div className="flex gap-4 mt-4 label-caps">
                <span className="flex items-center gap-1"><Heart size={12} /> {p.like_count}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- Story ----------
function StoryBlock({ story, artist }) {
  const socials = [
    story.website && { icon: <Globe size={14} />, label: "Website", value: story.website },
    story.instagram && { icon: <Instagram size={14} />, label: "Instagram", value: story.instagram },
    story.twitter && { icon: <Twitter size={14} />, label: "Twitter", value: story.twitter },
  ].filter(Boolean);
  return (
    <div className="glass-card p-8 md:p-12 rounded-sm max-w-4xl">
      <div className="grid md:grid-cols-3 gap-8 text-sm">
        {story.location && <StoryLine label="Based" value={story.location} />}
        {story.style && <StoryLine label="Style" value={story.style} />}
        {story.years_active && <StoryLine label="Active since" value={story.years_active} />}
        {story.education && <StoryLine label="Education" value={story.education} />}
        {story.exhibitions && <StoryLine label="Exhibitions" value={story.exhibitions} />}
        {story.awards && <StoryLine label="Awards" value={story.awards} />}
      </div>
      {story.influences && (
        <div className="mt-8 pt-8 border-t border-white/10">
          <div className="label-caps mb-2">Influences</div>
          <div className="text-zinc-200 leading-relaxed">{story.influences}</div>
        </div>
      )}
      {socials.length > 0 && (
        <div className="mt-8 pt-8 border-t border-white/10 flex flex-wrap gap-4">
          {socials.map((s, i) => <a key={i} href={s.value.startsWith("http") ? s.value : `https://${s.value}`} target="_blank" rel="noreferrer" className="label-caps flex items-center gap-2 hover:text-[color:var(--accent)]">{s.icon} {s.label}</a>)}
        </div>
      )}
    </div>
  );
}
function StoryLine({ label, value }) {
  return <div><div className="label-caps">{label}</div><div className="font-unbounded text-base mt-1">{value}</div></div>;
}

// ---------- Completed Commissions Rail (proof of work) ----------
function CompletedCommissionsRail({ artistId }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    api.get(`/artists/${artistId}/completed-commissions?limit=8`).then((r) => setItems(r.data)).catch(() => {});
  }, [artistId]);
  if (items.length === 0) return null;
  return (
    <div className="mt-8" data-testid="completed-commissions-rail">
      <div className="label-caps mb-4" style={{ color: "var(--accent)" }}>Past commissions · {items.length}</div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {items.map((c) => (
          <div key={c.id} data-testid={`completed-${c.id}`} className="border border-white/8 rounded-sm bg-[#121214] overflow-hidden hover-lift-card">
            <div className="aspect-square overflow-hidden bg-black">
              <img src={resolveImg(c.final_images?.[0])} className="w-full h-full object-cover" alt="" />
            </div>
            <div className="p-3">
              <div className="font-unbounded text-sm truncate">{c.subject}</div>
              <div className="label-caps mt-1" style={{ color: "var(--accent)" }}>Delivered</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- Commission ----------
function CommissionBlock({ artistId, artist, isOwner, blurb }) {
  return (
    <div className="glass-card p-10 rounded-sm relative overflow-hidden">
      <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full blur-3xl opacity-30" style={{ background: "var(--accent)" }} />
      <div className="relative">
        <div className="label-caps mb-3" style={{ color: "var(--accent)" }}><Palette size={12} className="inline mr-2" /> Available for commissions</div>
        <h3 className="font-anton text-3xl md:text-5xl uppercase leading-tight">Want something custom?</h3>
        <p className="text-zinc-300 mt-4 max-w-xl whitespace-pre-wrap">
          {blurb || `Send a brief with your budget, deadline, and any references. ${artist?.name || "The artist"} will respond within a few days. Use the Commission button in the header to send a request.`}
        </p>
      </div>
    </div>
  );
}

// ---------- Theme shell ----------
function StudioThemeShell({ theme, accent, config, children }) {
  const [themes, setThemes] = useState({});
  useEffect(() => {
    api.get("/studio/themes").then((r) => {
      const map = {}; r.data.forEach((t) => (map[t.id] = t));
      setThemes(map);
    });
  }, []);
  const t = themes[theme] || {};
  const finalAccent = accent || t.accent || "#CCFF00";
  const bg = config.background || {};
  const bgSrc = bg.type === "image" && bg.value ? bg.value :
                bg.type === "color" ? null :
                t.bg_url;
  const solidBg = bg.type === "color" ? bg.value : null;
  const texture = bg.texture || t.default_texture || "none";
  const textureOpacity = (bg.texture_opacity ?? 25) / 100;
  const styleVars = {
    "--accent": finalAccent,
    "--secondary": t.secondary || "#FF4D4D",
    "--surface": t.surface || "rgba(10,10,12,0.85)",
  };
  return (
    <div className="relative min-h-screen" style={{ ...styleVars, ...(solidBg ? { background: solidBg } : {}) }} data-theme={theme} data-testid="studio-shell">
      {bgSrc && (
        <div className="fixed inset-0 z-0 pointer-events-none">
          <img src={bgSrc} className="w-full h-full object-cover opacity-25" alt="" />
          <div className="absolute inset-0 bg-gradient-to-b from-[#0A0A0C]/70 via-[#0A0A0C]/80 to-[#0A0A0C]" />
        </div>
      )}
      {theme === "neon_digital" && (
        <div className="fixed inset-0 z-0 pointer-events-none opacity-20"
          style={{ backgroundImage: "linear-gradient(rgba(0,229,255,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(0,229,255,0.15) 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
      )}
      {theme === "dark_gallery" && (
        <div className="fixed inset-0 z-0 pointer-events-none"
          style={{ background: "radial-gradient(ellipse at center top, rgba(255,255,255,0.06), transparent 60%)" }} />
      )}
      {texture && texture !== "none" && (
        <TextureLayer texture={texture} opacity={textureOpacity} />
      )}
      <div className="relative z-10">{children}</div>
    </div>
  );
}

// ---------- Texture layer (SVG data-URIs — no external assets) ----------
function TextureLayer({ texture, opacity }) {
  const patterns = {
    brick: {
      // Red-orange brick pattern
      style: {
        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='40' viewBox='0 0 80 40'><rect width='80' height='40' fill='%23261815'/><rect x='0' y='0' width='38' height='18' fill='%234a2a24' stroke='%23161011' stroke-width='2'/><rect x='40' y='0' width='38' height='18' fill='%234a2a24' stroke='%23161011' stroke-width='2'/><rect x='-19' y='20' width='38' height='18' fill='%234a2a24' stroke='%23161011' stroke-width='2'/><rect x='21' y='20' width='38' height='18' fill='%234a2a24' stroke='%23161011' stroke-width='2'/><rect x='61' y='20' width='38' height='18' fill='%234a2a24' stroke='%23161011' stroke-width='2'/></svg>")`,
        backgroundSize: "160px 80px",
      },
    },
    concrete: {
      style: {
        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence baseFrequency='0.9' numOctaves='2' seed='4'/><feColorMatrix values='0 0 0 0 0.3, 0 0 0 0 0.3, 0 0 0 0 0.3, 0 0 0 0.4 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>")`,
        backgroundSize: "400px 400px",
      },
    },
    graffiti: {
      style: {
        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><g><path d='M 20 40 Q 60 20 100 60 T 200 80' stroke='%23CCFF00' stroke-width='6' fill='none' opacity='0.5'/><path d='M 40 160 Q 100 200 180 140' stroke='%23FF4D4D' stroke-width='4' fill='none' opacity='0.4'/><circle cx='240' cy='40' r='8' fill='%237C3AED' opacity='0.6'/><circle cx='60' cy='250' r='6' fill='%2300E5FF' opacity='0.5'/><path d='M 220 220 L 260 240 L 240 270 Z' fill='%23F5A623' opacity='0.4'/><text x='140' y='150' font-family='Arial Black' font-size='40' fill='%23FFFFFF' opacity='0.15' transform='rotate(-15, 140, 150)'>ART</text></g></svg>")`,
        backgroundSize: "600px 600px",
      },
    },
    grid: {
      style: {
        backgroundImage: `linear-gradient(rgba(0,229,255,${opacity}) 1px, transparent 1px), linear-gradient(90deg, rgba(0,229,255,${opacity}) 1px, transparent 1px)`,
        backgroundSize: "40px 40px",
      },
    },
    noise: {
      style: {
        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence baseFrequency='2' numOctaves='2' seed='7'/><feColorMatrix values='0 0 0 0 1, 0 0 0 0 1, 0 0 0 0 1, 0 0 0 0.5 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>")`,
        backgroundSize: "200px 200px",
      },
    },
    paper: {
      style: {
        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='400'><filter id='p'><feTurbulence baseFrequency='0.04' numOctaves='5' seed='2'/><feColorMatrix values='0 0 0 0 0.9, 0 0 0 0 0.85, 0 0 0 0 0.75, 0 0 0 0.15 0'/></filter><rect width='100%25' height='100%25' filter='url(%23p)'/></svg>")`,
        backgroundSize: "800px 800px",
      },
    },
  };
  const p = patterns[texture];
  if (!p) return null;
  return (
    <div className="fixed inset-0 z-0 pointer-events-none"
      data-testid={`texture-${texture}`}
      style={{ ...p.style, opacity, mixBlendMode: texture === "grid" ? "screen" : "overlay" }} />
  );
}
