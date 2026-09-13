import React from "react";
import { Sparkles, Crown } from "lucide-react";

export function FoundingBadge({ number, size = "sm" }) {
  const cls = size === "lg" ? "text-[11px] px-2.5 py-1 gap-1.5" : "text-[9px] px-1.5 py-0.5 gap-1";
  return (
    <span data-testid="founding-badge" title="Founding Artist — joined in Art Core's first chapter"
      className={`inline-flex items-center label-caps rounded-sm border border-[#CCFF00]/40 bg-[#CCFF00]/10 text-[#CCFF00] ${cls}`}>
      <Sparkles size={size === "lg" ? 12 : 9} /> Founding{number ? ` #${number}` : ""}
    </span>
  );
}

export function ProBadge({ size = "sm" }) {
  const cls = size === "lg" ? "text-[11px] px-2.5 py-1 gap-1.5" : "text-[9px] px-1.5 py-0.5 gap-1";
  return (
    <span data-testid="pro-badge" title="Art Core Pro member"
      className={`inline-flex items-center label-caps rounded-sm border border-[#7C3AED]/50 bg-[#7C3AED]/15 text-[#C4B5FD] ${cls}`}>
      <Crown size={size === "lg" ? 12 : 9} /> Pro
    </span>
  );
}

export function ArtistBadges({ artist, size = "sm" }) {
  if (!artist) return null;
  return (
    <span className="inline-flex items-center gap-1.5 flex-wrap">
      {artist.founding_member && <FoundingBadge number={size === "lg" ? artist.founding_number : null} size={size} />}
      {artist.pro_active && <ProBadge size={size} />}
    </span>
  );
}
