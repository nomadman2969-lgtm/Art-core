import React, { useEffect, useState } from "react";
import { Award } from "lucide-react";
import { api } from "../api";

export function BadgeRow({ userId }) {
  const [badges, setBadges] = useState([]);
  useEffect(() => { api.get(`/users/${userId}/badges`).then((r) => setBadges(r.data.filter((b) => b.earned))).catch(() => {}); }, [userId]);
  if (!badges.length) return null;
  return (
    <div data-testid="badge-row" className="flex flex-wrap gap-2 mt-5">
      {badges.map((b) => (
        <span key={b.id} data-testid={`badge-${b.id}`} title={b.desc}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] uppercase tracking-[0.15em] font-semibold border"
          style={{ borderColor: `${b.color}66`, background: `${b.color}1A`, color: b.color }}>
          <Award size={11} /> {b.label}
        </span>
      ))}
    </div>
  );
}
