import React from "react";
import { Link } from "react-router-dom";
import { thumbUrl } from "../api";
import { Heart, MessageCircle } from "lucide-react";

export const resolveImg = (p) => thumbUrl(p, 480);

export function ArtCard({ art, tall = false, wide = false }) {
  const aspect = wide ? "aspect-[4/3]" : tall ? "aspect-[3/4]" : "aspect-square";
  return (
    <Link to={`/artwork/${art.id}`} data-testid={`artcard-${art.id}`}
      className="block group relative overflow-hidden border border-white/8 hover-lift-card bg-[#121214] rounded-sm">
      <div className={`relative overflow-hidden ${aspect} bg-black`}>
        <img src={resolveImg(art.images?.[0])} alt={art.title} loading="lazy"
          className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/0 to-black/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        {art.status === "sold" && <div className="absolute top-3 left-3 badge-coral">Sold</div>}
        {art.aotw && <div className="absolute top-3 right-3 badge-lime">Featured ★</div>}
        <div className="absolute bottom-0 left-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <div className="font-unbounded text-white text-sm font-semibold truncate">{art.title}</div>
          <div className="flex items-center justify-between mt-1">
            <div className="text-xs text-zinc-300">{art.artist?.name}</div>
            <div className="text-xs text-[#CCFF00] font-bold">${Number(art.price).toLocaleString()}</div>
          </div>
        </div>
      </div>
      <div className="p-3 md:hidden">
        <div className="font-unbounded text-sm truncate">{art.title}</div>
        <div className="text-xs text-zinc-500 mt-0.5">{art.artist?.name}</div>
        <div className="text-xs text-[#CCFF00] font-bold mt-1">${Number(art.price).toLocaleString()}</div>
      </div>
      {(art.like_count != null || art.comment_count != null) && (
        <div className="absolute top-3 right-3 flex gap-2 md:opacity-0 group-hover:opacity-100 transition-opacity">
          {art.like_count > 0 && (
            <div className="flex items-center gap-1 text-xs text-white bg-black/60 backdrop-blur px-2 py-1 rounded-sm">
              <Heart size={11} /> {art.like_count}
            </div>
          )}
          {art.comment_count > 0 && (
            <div className="flex items-center gap-1 text-xs text-white bg-black/60 backdrop-blur px-2 py-1 rounded-sm">
              <MessageCircle size={11} /> {art.comment_count}
            </div>
          )}
        </div>
      )}
    </Link>
  );
}
