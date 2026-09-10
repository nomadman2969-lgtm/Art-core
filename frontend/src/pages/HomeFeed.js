import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, thumbUrl } from "../api";
import { toast } from "sonner";
import { Heart, MessageCircle, Share2, Bookmark, Sparkles, Users, ImagePlus, Palette, Filter, X, Plus, Calendar, MapPin } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { ReportButton } from "../components/ReportButton";
import { RecommendedEvents } from "../components/events/RecommendedEvents";
import FeedComposer from "../components/FeedComposer";

const resolveImg = (p) => thumbUrl(p, 960);

const POST_KIND_META = {
  update: { label: "Update", color: "#CCFF00" },
  wip: { label: "Work in Progress", color: "#F5A623" },
  studio_photo: { label: "Studio", color: "#7C3AED" },
  announcement: { label: "Announcement", color: "#00E5FF" },
  auction: { label: "Auction", color: "#FF4D4D" },
  sold: { label: "Sold", color: "#CCFF00" },
  commission: { label: "Commission", color: "#7C3AED" },
  exhibition: { label: "Exhibition", color: "#D4AF37" },
  behind_scenes: { label: "Behind the Scenes", color: "#FF6EC7" },
  event: { label: "Event", color: "#00E5FF" },
};

const FILTER_CHIPS = [
  { key: "artwork", label: "New Artwork", color: "#CCFF00" },
  { key: "wip", label: "WIP", color: "#F5A623" },
  { key: "auction", label: "Auctions", color: "#FF4D4D" },
  { key: "sold", label: "Sold", color: "#CCFF00" },
  { key: "exhibition", label: "Exhibitions", color: "#D4AF37" },
  { key: "behind_scenes", label: "BTS", color: "#FF6EC7" },
  { key: "announcement", label: "News", color: "#00E5FF" },
  { key: "commission", label: "Commissions", color: "#7C3AED" },
  { key: "event", label: "Events", color: "#00E5FF" },
];

// Simple @handle rendering — links to /artist/{id} isn't easy without resolving,
// so we just style them differently
function renderText(text) {
  if (!text) return null;
  const parts = text.split(/(@[a-zA-Z0-9_\-\.]{2,32})/g);
  return parts.map((p, i) =>
    p.startsWith("@") ? <span key={i} className="text-[#CCFF00]">{p}</span> : <span key={i}>{p}</span>
  );
}

export default function HomeFeed() {
  const { user } = useAuth();
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeFilters, setActiveFilters] = useState([]);
  const [composerOpen, setComposerOpen] = useState(false);
  const [nearbyEvents, setNearbyEvents] = useState([]);

  const canPost = user?.role === "artist" || user?.role === "admin";

  // Fetch trending upcoming events (RSVP-velocity-ranked, location-aware if permitted)
  useEffect(() => {
    const fetchTrending = (params) => {
      const qs = new URLSearchParams(params).toString();
      api.get(`/events/lists/trending${qs ? `?${qs}` : ""}`)
        .then((r) => setNearbyEvents(r.data.slice(0, 8)))
        .catch(() => setNearbyEvents([]));
    };
    if (typeof navigator !== "undefined" && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => fetchTrending({ near_lat: String(pos.coords.latitude), near_lng: String(pos.coords.longitude), radius_km: "100" }),
        () => fetchTrending({}),
        { timeout: 4000, maximumAge: 10 * 60 * 1000 }
      );
    } else {
      fetchTrending({});
    }
  }, []);

  const load = (filters = activeFilters) => {
    setLoading(true);
    const q = filters.length > 0 ? `?kinds=${filters.join(",")}` : "";
    api.get(`/feed/home${q}`).then((r) => setFeed(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const toggleFilter = (key) => {
    const next = activeFilters.includes(key)
      ? activeFilters.filter((f) => f !== key)
      : [...activeFilters, key];
    setActiveFilters(next);
    load(next);
  };
  const clearFilters = () => { setActiveFilters([]); load([]); };

  if (loading && !feed) return <div className="py-32 text-center label-caps text-zinc-500">Loading your feed...</div>;
  return (
    <div data-testid="home-feed" className="max-w-2xl mx-auto px-4 md:px-6 pt-10 pb-32">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="label-caps text-[#CCFF00]"><Users size={12} className="inline mr-2" /> Home Feed</div>
          <h1 className="font-anton text-5xl md:text-6xl uppercase mt-3">Your Feed</h1>
          <div className="text-zinc-500 mt-2">
            {feed.following_count > 0
              ? `Latest from ${feed.following_count} artist${feed.following_count === 1 ? "" : "s"} you follow.`
              : "You're not following any artists yet. Explore below to fill your feed."}
          </div>
        </div>
        {canPost && (
          <button
            data-testid="open-composer-btn"
            onClick={() => setComposerOpen(true)}
            className="btn-lime !py-2 !px-3 flex items-center gap-2 flex-shrink-0 mt-2">
            <ImagePlus size={14} />
            <span className="hidden md:inline">New Post</span>
          </button>
        )}
      </div>

      {/* Quick-post prompt card for artists */}
      {canPost && (
        <button
          data-testid="composer-prompt"
          onClick={() => setComposerOpen(true)}
          className="w-full text-left mb-6 border border-white/8 rounded-sm p-4 flex items-center gap-3 hover:border-[#CCFF00]/40 transition-colors bg-[#121214]">
          <div className="w-10 h-10 rounded-full bg-[#CCFF00]/20 flex items-center justify-center font-anton text-lg flex-shrink-0">
            {user?.name?.[0]?.toUpperCase() || "A"}
          </div>
          <div className="text-sm text-zinc-500 flex-1">Share a WIP, drop new work, tag a collector...</div>
          <div className="btn-ghost !py-1.5 !px-3 flex items-center gap-1 text-xs">
            <Plus size={12} /> Post
          </div>
        </button>
      )}

      <RecommendedEvents />

      {/* Trending upcoming events rail */}
      {nearbyEvents.length > 0 && (
        <div className="mb-6" data-testid="events-rail">
          <div className="flex items-center justify-between mb-3">
            <div className="label-caps text-[#FF4D4D] flex items-center gap-2"><MapPin size={12} /> Trending Events</div>
            <Link to="/events" className="label-caps text-xs text-zinc-500 hover:text-[#CCFF00]">See all →</Link>
          </div>
          <div className="flex gap-3 overflow-x-auto scrollbar-none -mx-4 px-4 md:mx-0 md:px-0 pb-2">
            {nearbyEvents.map((e) => (
              <Link
                key={e.id}
                to={`/events/${e.id}`}
                data-testid={`rail-event-${e.id}`}
                className="flex-shrink-0 w-56 border border-white/8 rounded-sm bg-[#121214] hover:border-[#CCFF00]/40 transition-colors overflow-hidden">
                <div className="h-24 flex items-center justify-center relative"
                  style={{ background: e.cover_image ? undefined : "linear-gradient(135deg, #FF4D4D30, #0A0A0C)" }}>
                  {e.cover_image ? (
                    <img
                      src={e.cover_image.startsWith("http") ? e.cover_image : `${process.env.REACT_APP_BACKEND_URL}/api/files/${e.cover_image}`}
                      alt="" className="w-full h-full object-cover" loading="lazy" />
                  ) : (
                    <MapPin size={22} className="text-white/50" />
                  )}
                  <div className="absolute top-2 left-2 label-caps text-[10px] px-1.5 py-0.5 rounded-sm bg-black/70 text-white">
                    {(e.category || "").replace(/_/g, " ")}
                  </div>
                  {e.recent_rsvps_48h >= 3 && (
                    <div className="absolute bottom-2 left-2 label-caps text-[10px] px-1.5 py-0.5 rounded-sm bg-[#FF4D4D]/90 text-white flex items-center gap-1">
                      🔥 Trending
                    </div>
                  )}
                  {!e.is_free && (
                    <div className="absolute top-2 right-2 label-caps text-[10px] px-1.5 py-0.5 rounded-sm bg-[#F5A623] text-black">
                      ${e.ticket_price}
                    </div>
                  )}
                </div>
                <div className="p-3">
                  <div className="font-unbounded font-semibold text-sm truncate">{e.title}</div>
                  <div className="text-xs text-zinc-500 flex items-center gap-1 mt-1">
                    <Calendar size={10} /> {new Date(e.start_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                  </div>
                  <div className="text-xs text-zinc-500 flex items-center gap-1 truncate">
                    <MapPin size={10} /> {e.location?.city || e.location?.address || "TBA"}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Filter chips */}
      <div className="mb-6 -mx-4 md:-mx-6 px-4 md:px-6 overflow-x-auto scrollbar-none" data-testid="feed-filters">
        <div className="flex gap-2 items-center pb-2 flex-nowrap">
          <span className="label-caps text-zinc-500 flex items-center gap-1 flex-shrink-0"><Filter size={12} /> Filter</span>
          {FILTER_CHIPS.map((c) => {
            const active = activeFilters.includes(c.key);
            return (
              <button key={c.key} data-testid={`filter-${c.key}`} onClick={() => toggleFilter(c.key)}
                className="label-caps text-xs px-3 py-1.5 rounded-full border flex-shrink-0 transition-colors"
                style={{
                  borderColor: active ? c.color : "rgba(255,255,255,0.12)",
                  background: active ? `${c.color}20` : "transparent",
                  color: active ? c.color : "#A1A1AA",
                }}>{c.label}</button>
            );
          })}
          {activeFilters.length > 0 && (
            <button data-testid="filter-clear" onClick={clearFilters} className="label-caps text-xs text-zinc-500 hover:text-white flex-shrink-0 flex items-center gap-1">
              <X size={11} /> Clear
            </button>
          )}
        </div>
      </div>

      {feed.items.length === 0 ? (
        <div className="border border-dashed border-white/10 py-24 text-center rounded-sm">
          <Sparkles size={32} className="mx-auto text-zinc-600" />
          <div className="label-caps mt-4 text-zinc-500">
            {activeFilters.length > 0 ? "Nothing matches these filters" : "Nothing here yet"}
          </div>
          {activeFilters.length > 0 ? (
            <button onClick={clearFilters} className="btn-ghost mt-6">Clear Filters</button>
          ) : (
            <Link to="/artists" className="btn-lime mt-6 inline-flex">Discover Artists</Link>
          )}
        </div>
      ) : (
        <div className="space-y-6">
          {feed.items.map((it) => (
            it.timeline_kind === "post"
              ? <PostCard key={`p-${it.id}`} post={it} onChange={load} />
              : <ArtworkFeedCard key={`a-${it.id}`} art={it} onChange={load} />
          ))}
        </div>
      )}

      {/* Floating "New Post" button (mobile-first) for artists */}
      {canPost && (
        <button
          data-testid="fab-new-post"
          onClick={() => setComposerOpen(true)}
          className="fixed bottom-6 right-6 z-30 w-14 h-14 rounded-full bg-[#CCFF00] text-black shadow-2xl flex items-center justify-center hover:scale-110 transition-transform md:hidden"
          aria-label="New Post">
          <Plus size={22} />
        </button>
      )}

      {composerOpen && (
        <FeedComposer onClose={() => setComposerOpen(false)} onCreated={() => load()} />
      )}
    </div>
  );
}

function TimeAgo({ iso }) {
  if (!iso) return null;
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return <span>just now</span>;
  if (m < 60) return <span>{m}m ago</span>;
  const h = Math.floor(m / 60);
  if (h < 24) return <span>{h}h ago</span>;
  const d = Math.floor(h / 24);
  if (d < 7) return <span>{d}d ago</span>;
  return <span>{new Date(iso).toLocaleDateString()}</span>;
}

function PostCard({ post, onChange }) {
  const meta = POST_KIND_META[post.kind] || POST_KIND_META.update;
  const [liked, setLiked] = useState(!!post.liked);
  const [likeCount, setLikeCount] = useState(post.like_count || 0);
  const toggleLike = async () => {
    try {
      if (liked) { await api.delete(`/posts/${post.id}/like`); setLiked(false); setLikeCount((c) => Math.max(0, c - 1)); }
      else { await api.post(`/posts/${post.id}/like`); setLiked(true); setLikeCount((c) => c + 1); }
    } catch (e) { toast.error("Failed"); }
  };
  return (
    <article data-testid={`post-${post.id}`} className="border border-white/8 rounded-sm bg-[#121214] overflow-hidden">
      <div className="p-4 flex items-center gap-3">
        <Link to={`/artist/${post.artist?.id}`} className="w-11 h-11 rounded-full bg-[#7C3AED]/30 flex items-center justify-center font-anton text-lg flex-shrink-0">
          {post.artist?.name?.[0]?.toUpperCase() || "A"}
        </Link>
        <div className="flex-1 min-w-0">
          <Link to={`/artist/${post.artist?.id}`} className="font-unbounded font-semibold hover:text-[#CCFF00]">{post.artist?.name}</Link>
          <div className="text-xs text-zinc-500 flex items-center gap-2 flex-wrap">
            <span className="label-caps px-2 py-0.5 rounded-sm" style={{ background: `${meta.color}20`, color: meta.color }}>{meta.label}</span>
            · <TimeAgo iso={post.created_at} />
            {post.pinned && <span className="label-caps text-[#F5A623]">· Pinned</span>}
          </div>
        </div>
        <ReportButton targetType="post" targetId={post.id} ownerId={post.artist?.id} compact />
      </div>
      {post.video ? (
        <video data-testid={`post-video-${post.id}`} src={resolveImg(post.video)} controls playsInline preload="metadata"
          className="w-full max-h-[80vh] bg-black object-contain" />
      ) : post.image ? (
        <img src={resolveImg(post.image)} className="w-full max-h-[70vh] object-cover bg-black" alt="" loading="lazy" />
      ) : null}
      <div className="p-4">
        <div className="text-zinc-100 whitespace-pre-wrap leading-relaxed">{renderText(post.text)}</div>
        <div className="flex items-center gap-5 mt-4 pt-4 border-t border-white/8">
          <button data-testid={`post-like-${post.id}`} onClick={toggleLike} className="flex items-center gap-2 label-caps hover:text-[#FF4D4D] transition-colors">
            <Heart size={16} fill={liked ? "#FF4D4D" : "none"} color={liked ? "#FF4D4D" : "currentColor"} />
            <span>{likeCount}</span>
          </button>
          <Link to={`/artist/${post.artist?.id}#post-${post.id}`} className="flex items-center gap-2 label-caps hover:text-[#CCFF00]">
            <MessageCircle size={16} />
            <span>{post.comment_count || 0}</span>
          </Link>
        </div>
      </div>
    </article>
  );
}

function ArtworkFeedCard({ art, onChange }) {
  const [liked, setLiked] = useState(!!art.liked);
  const [saved, setSaved] = useState(!!art.saved);
  const [likeCount, setLikeCount] = useState(art.like_count || 0);
  const toggleLike = async (e) => {
    e.preventDefault();
    try {
      if (liked) { await api.delete(`/artworks/${art.id}/like`); setLiked(false); setLikeCount((c) => Math.max(0, c - 1)); }
      else { await api.post(`/artworks/${art.id}/like`); setLiked(true); setLikeCount((c) => c + 1); }
    } catch { toast.error("Failed"); }
  };
  const toggleSave = async (e) => {
    e.preventDefault();
    try {
      if (saved) { await api.delete(`/artworks/${art.id}/save`); setSaved(false); toast("Removed from saved"); }
      else { await api.post(`/artworks/${art.id}/save`, {}); setSaved(true); toast.success("Saved"); }
    } catch { toast.error("Failed"); }
  };
  const share = async (e) => {
    e.preventDefault();
    const url = `${window.location.origin}/artwork/${art.id}`;
    try { await navigator.clipboard.writeText(url); } catch {}
    await api.post(`/artworks/${art.id}/share`, { target: "copy_link" }).catch(() => {});
    toast.success("Link copied");
  };
  return (
    <article data-testid={`feed-art-${art.id}`} className="border border-white/8 rounded-sm bg-[#121214] overflow-hidden">
      <div className="p-4 flex items-center gap-3">
        <Link to={`/artist/${art.artist?.id}`} className="w-11 h-11 rounded-full bg-[#CCFF00]/30 flex items-center justify-center font-anton text-lg flex-shrink-0">
          {art.artist?.name?.[0]?.toUpperCase() || "A"}
        </Link>
        <div className="flex-1 min-w-0">
          <Link to={`/artist/${art.artist?.id}`} className="font-unbounded font-semibold hover:text-[#CCFF00]">{art.artist?.name}</Link>
          <div className="text-xs text-zinc-500 flex items-center gap-2">
            <span className="label-caps px-2 py-0.5 rounded-sm" style={{ background: "#CCFF0020", color: "#CCFF00" }}>
              <Palette size={10} className="inline mr-1" /> New Artwork
            </span>
            · <TimeAgo iso={art.created_at} />
          </div>
        </div>
      </div>
      <Link to={`/artwork/${art.id}`} className="block relative group">
        <img src={resolveImg(art.images?.[0])} className="w-full max-h-[80vh] object-cover bg-black" alt={art.title} loading="lazy" />
      </Link>
      <div className="p-4">
        <Link to={`/artwork/${art.id}`}>
          <div className="font-anton text-2xl uppercase leading-tight">{art.title}</div>
          <div className="text-xs text-zinc-500 mt-1">{art.medium} · <span className="text-[#CCFF00] font-anton">${Number(art.price).toLocaleString()}</span></div>
        </Link>
        {art.description && <p className="text-sm text-zinc-300 mt-3 line-clamp-3">{art.description}</p>}
        <div className="flex items-center gap-4 mt-4 pt-4 border-t border-white/8">
          <button data-testid={`art-like-${art.id}`} onClick={toggleLike} className="flex items-center gap-2 label-caps hover:text-[#FF4D4D]">
            <Heart size={16} fill={liked ? "#FF4D4D" : "none"} color={liked ? "#FF4D4D" : "currentColor"} />
            <span>{likeCount}</span>
          </button>
          <Link to={`/artwork/${art.id}#comments`} className="flex items-center gap-2 label-caps hover:text-[#CCFF00]">
            <MessageCircle size={16} /> <span>{art.comment_count || 0}</span>
          </Link>
          <button data-testid={`art-share-${art.id}`} onClick={share} className="flex items-center gap-2 label-caps hover:text-[#7C3AED]">
            <Share2 size={16} />
          </button>
          <button data-testid={`art-save-${art.id}`} onClick={toggleSave} className="flex items-center gap-2 label-caps hover:text-[#CCFF00] ml-auto">
            <Bookmark size={16} fill={saved ? "#CCFF00" : "none"} color={saved ? "#CCFF00" : "currentColor"} />
            <span>{saved ? "Saved" : "Save"}</span>
          </button>
        </div>
      </div>
    </article>
  );
}
