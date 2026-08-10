import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Trophy } from "lucide-react";

export function RankBadge({ tier, color, small }) {
  if (!tier) return null;
  const size = small ? "text-[9px] px-1.5 py-0.5" : "text-xs px-2.5 py-1";
  return (
    <span data-testid={`rank-badge-${tier}`} className={`inline-flex items-center gap-1 font-unbounded font-bold uppercase rounded-sm ${size}`}
      style={{ background: `${color}20`, color, border: `1px solid ${color}60` }}>
      <Trophy size={small ? 8 : 10} /> {tier}
    </span>
  );
}

export default function Rankings() {
  const [board, setBoard] = useState([]);
  const [tiers, setTiers] = useState([]);
  useEffect(() => {
    api.get("/rankings/leaderboard").then((r) => setBoard(r.data));
    api.get("/rankings/tiers").then((r) => setTiers(r.data));
  }, []);
  return (
    <div data-testid="rankings-page" className="max-w-[1400px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="mb-12">
        <div className="label-caps text-[#CCFF00]"><Trophy size={12} className="inline mr-2" /> Leaderboard</div>
        <h1 className="font-anton text-6xl md:text-9xl uppercase mt-4 leading-[0.85]">Rankings</h1>
        <p className="text-zinc-400 mt-4 max-w-xl">Bronze to Legendary — earned through sales, followers, likes, artworks, and completed commissions.</p>
      </div>

      {/* Tier legend */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-16">
        {tiers.map((t) => (
          <div key={t.name} data-testid={`tier-${t.name}`} className="glass-card p-4 text-center rounded-sm">
            <Trophy size={20} style={{ color: t.color }} className="mx-auto" />
            <div className="font-unbounded font-bold mt-2 text-sm uppercase" style={{ color: t.color }}>{t.name}</div>
            <div className="label-caps mt-1 !text-[9px]">{t.min}+ pts</div>
          </div>
        ))}
      </div>

      {board.length === 0 ? (
        <div className="border border-dashed border-white/10 py-24 text-center label-caps text-zinc-500 rounded-sm">No ranked artists yet.</div>
      ) : (
        <div className="border border-white/8 rounded-sm divide-y divide-white/8">
          {board.map((r, i) => (
            <Link key={r.id} to={`/artist/${r.id}`} data-testid={`board-row-${r.id}`}
              className="flex items-center gap-4 p-4 hover:bg-white/[0.03] transition-colors">
              <div className="font-anton text-3xl w-12 text-center" style={{ color: i < 3 ? "#CCFF00" : "#52525B" }}>
                {i + 1}
              </div>
              <div className="avatar-ring w-12 h-12">
                <div className="bg-[#0A0A0C] rounded-full w-full h-full flex items-center justify-center font-anton text-lg uppercase">
                  {r.name?.[0]}
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-unbounded font-semibold">{r.name}</div>
                <div className="label-caps mt-0.5">
                  {r.breakdown.sales} sales · {r.breakdown.followers} followers · {r.breakdown.likes_received} likes
                </div>
              </div>
              <RankBadge tier={r.tier} color={r.tier_color} />
              <div className="font-anton text-2xl w-24 text-right text-[#CCFF00]">{r.score}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
