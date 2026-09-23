import React, { useEffect, useState } from "react";
import { api } from "../api";
import { ArtCard } from "../components/ArtCard";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Heart } from "lucide-react";
import { useTranslation } from "react-i18next";
import { EmptyState } from "../components/EmptyState";

export default function Explore() {
  const { t } = useTranslation();
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    api.get("/feed?limit=60").then((r) => setFeed(r.data)).finally(() => setLoading(false));
  }, []);

  const toggleLike = async (art) => {
    if (!user) { toast("Sign in to like"); return; }
    try {
      if (art.liked) {
        await api.delete(`/artworks/${art.id}/like`);
        setFeed((f) => f.map((x) => x.id === art.id ? { ...x, liked: false, like_count: (x.like_count || 1) - 1 } : x));
      } else {
        await api.post(`/artworks/${art.id}/like`);
        setFeed((f) => f.map((x) => x.id === art.id ? { ...x, liked: true, like_count: (x.like_count || 0) + 1 } : x));
      }
    } catch { toast.error("Try again"); }
  };

  return (
    <div data-testid="explore-page" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="mb-12">
        <div className="label-caps text-[#CCFF00]">{t("explore.kicker")}</div>
        <h1 className="font-anton text-6xl md:text-9xl uppercase mt-4 leading-[0.85]">{t("explore.title")}</h1>
        <p className="text-zinc-400 mt-4 max-w-xl">{t("explore.sub")}</p>
      </div>

      {loading ? (
        <div className="text-zinc-500 py-24 text-center label-caps">{t("common.loading")}</div>
      ) : feed.length === 0 ? (
        <EmptyState icon="sparkles" title="Nothing here yet" body="Art Core is brand new — the first artists are setting up their studios right now. Are you an artist? Founding members lock in a 4% fee for life." cta="Join as an artist" to="/register?role=artist" secondary="How it works" secondaryTo="/how-it-works" testId="explore-empty" />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {feed.map((a, i) => (
            <div key={a.id} className="relative">
              <ArtCard art={a} tall={i % 7 === 0} />
              <button
                data-testid={`feed-like-${a.id}`}
                onClick={(e) => { e.preventDefault(); toggleLike(a); }}
                className="absolute top-3 left-3 z-10 bg-black/60 backdrop-blur border border-white/10 rounded-sm px-2 py-1 flex items-center gap-1 text-xs hover:border-[#FF4D4D] transition-colors">
                <Heart size={12} fill={a.liked ? "#FF4D4D" : "none"} color={a.liked ? "#FF4D4D" : "#fff"} />
                <span>{a.like_count || 0}</span>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
