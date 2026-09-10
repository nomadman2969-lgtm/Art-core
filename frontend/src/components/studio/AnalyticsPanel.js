import React from "react";
import { Link } from "react-router-dom";
import { Eye, Bookmark, Heart, TrendingUp, Users } from "lucide-react";
import { fileUrl } from "../../api";
import { SectionH, Stat } from "./StudioParts";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

function Bars({ data, valueKey, accent, testid }) {
  const max = Math.max(1, ...data.map((d) => d[valueKey]));
  return (
    <div className="flex items-end gap-1 h-28" data-testid={testid}>
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1 min-w-0 group" title={`${d.label}: ${d[valueKey]}`}>
          <div className="w-full rounded-t-sm transition-[height] duration-500" style={{ height: `${Math.max(3, (d[valueKey] / max) * 100)}%`, background: accent, opacity: 0.45 + 0.55 * (d[valueKey] / max) }} />
          <div className="text-[8px] text-zinc-600 truncate w-full text-center hidden sm:block">{d.label.split(" ")[1]}</div>
        </div>
      ))}
    </div>
  );
}

function TopViewed({ items }) {
  if (!items?.length) return <div className="text-zinc-500 label-caps py-8 text-center">No views tracked yet — share your studio link to get eyes on your work.</div>;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="top-viewed-grid">
      {items.map((a, i) => (
        <Link key={a.id} to={`/artwork/${a.id}`} className="border border-white/8 rounded-sm hover-lift-card block relative">
          <div className="absolute top-2 left-2 z-10 font-anton text-lg text-[#CCFF00] drop-shadow">#{i + 1}</div>
          <img src={resolveImg(a.images?.[0])} className="w-full aspect-square object-cover" alt="" />
          <div className="p-3">
            <div className="font-unbounded text-sm truncate">{a.title}</div>
            <div className="flex gap-3 mt-2 text-[10px] text-zinc-400">
              <span className="flex items-center gap-1"><Eye size={10} /> {a.views}</span>
              <span className="flex items-center gap-1"><Bookmark size={10} /> {a.saves}</span>
              <span className="flex items-center gap-1 text-[#FF4D4D]"><Heart size={10} /> {a.likes}</span>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}

export function AnalyticsPanel({ analytics }) {
  const a = analytics;
  const growth = a.follower_growth || [];
  const delta = growth.length ? growth[growth.length - 1].followers - growth[0].followers : 0;
  return (
    <div className="space-y-10" data-testid="analytics-panel">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
        <Stat label="Studio visits" value={a.visits} accent="#CCFF00" />
        <Stat label="Artwork views" value={a.total_views ?? 0} accent="#00E5FF" />
        <Stat label="Saves" value={a.total_saves ?? 0} accent="#F5A623" />
        <Stat label="Followers" value={a.followers} accent="#7C3AED" />
        <Stat label="Likes" value={a.total_likes} accent="#FF4D4D" />
        <Stat label="Sales" value={a.sales} accent="#00E5FF" />
        <Stat label="Revenue" value={`$${a.revenue.toLocaleString()}`} accent="#F5A623" />
        <Stat label="Artworks" value={a.artworks_count} accent="#FFFFFF" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="glass-card p-6 rounded-sm">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="label-caps text-zinc-400 flex items-center gap-2"><Eye size={12} /> Studio visits · last 14 days</div>
            <div className="font-unbounded text-sm text-[#CCFF00]" data-testid="visits-14d">{a.visits_14d ?? 0}</div>
          </div>
          <div className="mt-5"><Bars data={a.visit_series || []} valueKey="visits" accent="#CCFF00" testid="visits-chart" /></div>
        </div>
        <div className="glass-card p-6 rounded-sm">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="label-caps text-zinc-400 flex items-center gap-2"><Users size={12} /> Follower growth · 8 weeks</div>
            <div className="font-unbounded text-sm flex items-center gap-1" data-testid="follower-delta" style={{ color: delta >= 0 ? "#CCFF00" : "#FF4D4D" }}>
              <TrendingUp size={12} /> {delta >= 0 ? "+" : ""}{delta} <span className="text-zinc-500 text-[10px] font-normal">· {a.new_followers_30d ?? 0} new in 30d</span>
            </div>
          </div>
          <div className="mt-5"><Bars data={growth} valueKey="followers" accent="#7C3AED" testid="followers-chart" /></div>
        </div>
      </div>

      <SectionH title="Most viewed pieces"><TopViewed items={a.top_viewed} /></SectionH>

      <SectionH title="Most liked pieces">
        {a.top_artworks.length === 0 ? (
          <div className="text-zinc-500 label-caps py-8 text-center">No liked artworks yet.</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {a.top_artworks.map((t) => (
              <Link key={t.id} to={`/artwork/${t.id}`} className="border border-white/8 rounded-sm hover-lift-card block">
                <img src={resolveImg(t.images?.[0])} className="w-full aspect-square object-cover" alt="" />
                <div className="p-3">
                  <div className="font-unbounded text-sm truncate">{t.title}</div>
                  <div className="label-caps mt-1 text-[#FF4D4D]">♥ {t.likes}</div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </SectionH>
    </div>
  );
}
