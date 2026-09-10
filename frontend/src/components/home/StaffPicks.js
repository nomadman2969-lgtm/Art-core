import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Star, Calendar, MapPin } from "lucide-react";
import { api, thumbUrl } from "../../api";
import { ArtCard } from "../ArtCard";

export function StaffPicks({ compact = false }) {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/staff-picks").then((r) => setData(r.data)).catch(() => {}); }, []);
  if (!data || (data.artworks.length === 0 && data.events.length === 0)) return null;
  return (
    <section data-testid="staff-picks" className={compact ? "mb-8" : "max-w-[1600px] mx-auto px-6 md:px-12 py-16 md:py-24"}>
      <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
        <div>
          <div className="label-caps text-[#D4AF37] flex items-center gap-2"><Star size={12} /> Curated weekly</div>
          <h2 className={`font-anton uppercase mt-2 ${compact ? "text-2xl" : "text-4xl md:text-6xl"}`} data-testid="staff-picks-title">{data.title}</h2>
          {data.blurb && <p className="text-zinc-400 text-sm mt-2 max-w-xl">{data.blurb}</p>}
        </div>
        {data.updated_at && <div className="text-xs text-zinc-600 label-caps">Updated {new Date(data.updated_at).toLocaleDateString()}</div>}
      </div>
      {data.artworks.length > 0 && (
        <div className={`grid gap-4 ${compact ? "grid-cols-2" : "grid-cols-2 md:grid-cols-3 lg:grid-cols-4"}`} data-testid="staff-picks-artworks">
          {data.artworks.slice(0, compact ? 4 : 12).map((a) => <ArtCard key={a.id} art={a} />)}
        </div>
      )}
      {data.events.length > 0 && (
        <div className="flex gap-3 overflow-x-auto scrollbar-none pb-2 mt-6" data-testid="staff-picks-events">
          {data.events.map((e) => (
            <Link key={e.id} to={`/events/${e.id}`} className="flex-shrink-0 w-[260px] border border-[#D4AF37]/30 rounded-sm overflow-hidden bg-[#0F0F11] hover:border-[#D4AF37]">
              <div className="h-28 bg-white/[0.03]">{e.cover_image && <img src={thumbUrl(e.cover_image, 480)} alt="" loading="lazy" className="w-full h-full object-cover" />}</div>
              <div className="p-3">
                <div className="text-[10px] text-[#D4AF37] label-caps flex items-center gap-1"><Calendar size={10} /> {new Date(e.start_at).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</div>
                <div className="font-unbounded text-xs font-semibold mt-1 line-clamp-2">{e.title}</div>
                <div className="text-[11px] text-zinc-500 mt-1 truncate flex items-center gap-1"><MapPin size={10} /> {e.venue || e.location?.city || "TBA"}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
