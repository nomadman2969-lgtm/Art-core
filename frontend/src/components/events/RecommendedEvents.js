import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles, MapPin } from "lucide-react";
import { api, thumbUrl } from "../../api";
import { useAuth } from "../../context/AuthContext";

export function RecommendedEvents() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  useEffect(() => { if (user) api.get("/events/recommended").then((r) => setItems(r.data)).catch(() => setItems([])); }, [user?.id]); // eslint-disable-line
  if (!user || items.length === 0) return null;
  return (
    <div className="mb-8" data-testid="recommended-rail">
      <div className="flex items-center justify-between mb-3">
        <div className="label-caps text-[#CCFF00] flex items-center gap-2"><Sparkles size={12} /> Picked for you</div>
        <Link to="/events" className="label-caps text-xs text-zinc-500 hover:text-[#CCFF00]">All events →</Link>
      </div>
      <div className="flex gap-3 overflow-x-auto scrollbar-none -mx-4 px-4 md:mx-0 md:px-0 pb-2">
        {items.map((e) => (
          <Link key={e.id} to={`/events/${e.id}`} data-testid={`recommended-${e.id}`} className="flex-shrink-0 w-[240px] border border-white/8 rounded-sm overflow-hidden bg-[#0F0F11] hover:border-[#CCFF00]/40 transition-colors">
            <div className="h-28 bg-white/[0.03] relative">
              {e.cover_image && <img src={thumbUrl(e.cover_image, 480)} alt="" loading="lazy" className="w-full h-full object-cover" />}
              <div className="absolute bottom-1.5 left-1.5 label-caps text-[9px] px-1.5 py-0.5 rounded-sm bg-black/70 text-[#CCFF00]">{e.reason}</div>
            </div>
            <div className="p-3">
              <div className="text-[10px] text-zinc-500 label-caps">{new Date(e.start_at).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</div>
              <div className="font-unbounded text-xs font-semibold mt-1 line-clamp-2">{e.title}</div>
              <div className="text-[11px] text-zinc-500 mt-1 truncate flex items-center gap-1"><MapPin size={10} /> {e.venue || e.location?.city || "TBA"}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
