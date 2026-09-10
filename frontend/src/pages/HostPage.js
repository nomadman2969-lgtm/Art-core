import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Calendar, Users, MapPin, UserPlus, UserCheck, Palette, Share2 } from "lucide-react";
import { toast } from "sonner";
import { api, thumbUrl, fileUrl } from "../api";
import { useAuth } from "../context/AuthContext";
import { EventCard } from "./Events";
import { ReportButton } from "../components/ReportButton";

export default function HostPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [cats, setCats] = useState([]);
  const [tab, setTab] = useState("upcoming");
  const [busy, setBusy] = useState(false);

  const load = () => api.get(`/events/hosts/${id}`).then((r) => setData(r.data)).catch(() => setData(false));
  useEffect(() => { load(); api.get("/events/meta/categories").then((r) => setCats(r.data)).catch(() => {}); }, [id]); // eslint-disable-line
  const catMeta = (k) => cats.find((c) => c.key === k) || { label: k, color: "#A1A1AA" };

  const follow = async () => {
    if (!user) return toast.error("Log in to follow");
    setBusy(true);
    try {
      if (data.is_following) await api.delete(`/users/${id}/follow`); else await api.post(`/users/${id}/follow`);
      toast.success(data.is_following ? "Unfollowed" : `Following ${data.host.name} — you'll see their events first`);
      load();
    } catch { toast.error("Failed"); }
    setBusy(false);
  };
  const share = () => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/share/studio/${id}`;
    if (navigator.share) navigator.share({ title: `${data.host.name} · Events`, url }).catch(() => {});
    else { navigator.clipboard?.writeText(url); toast.success("Link copied"); }
  };

  if (data === null) return <div className="py-32 text-center label-caps text-zinc-500">Loading…</div>;
  if (data === false) return <div className="py-32 text-center label-caps text-zinc-500">Host not found</div>;
  const { host, stats, upcoming, past } = data;
  const list = tab === "upcoming" ? upcoming : past;

  return (
    <div data-testid="host-page" className="max-w-7xl mx-auto px-4 md:px-6 pt-6 md:pt-10 pb-32">
      <Link to="/events" className="label-caps text-zinc-500 hover:text-[#CCFF00] inline-flex items-center gap-1 mb-4"><ArrowLeft size={12} /> Events</Link>
      <div className="relative border border-white/8 rounded-sm overflow-hidden">
        <div className="h-44 md:h-64 bg-cover bg-center" style={{ backgroundImage: host.cover_image ? `url(${fileUrl(host.cover_image)})` : "linear-gradient(135deg,#7C3AED33,#0A0A0C)" }} />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0C] via-[#0A0A0C]/60 to-transparent" />
        <div className="relative -mt-16 md:-mt-20 px-5 md:px-8 pb-6 flex flex-col md:flex-row md:items-end gap-4">
          <div className="w-24 h-24 md:w-32 md:h-32 rounded-sm border-2 border-[#0A0A0C] bg-[#1a1a1d] overflow-hidden flex items-center justify-center font-anton text-4xl flex-shrink-0">
            {host.avatar ? <img src={thumbUrl(host.avatar, 240)} alt="" className="w-full h-full object-cover" /> : host.name?.[0]}
          </div>
          <div className="flex-1 min-w-0">
            <div className="label-caps text-[#FF4D4D]">Event host{host.is_artist ? " · Artist" : ""}</div>
            <h1 className="font-anton text-4xl sm:text-5xl lg:text-6xl uppercase leading-[0.9] mt-1" data-testid="host-name">{host.name}</h1>
            {host.location && <div className="text-xs text-zinc-400 mt-2 flex items-center gap-1"><MapPin size={11} /> {host.location}</div>}
            {host.bio && <p className="text-sm text-zinc-400 mt-2 max-w-2xl line-clamp-2">{host.bio}</p>}
          </div>
          <div className="flex gap-2 flex-wrap">
            {user?.id !== host.id && (
              <button data-testid="host-follow-btn" onClick={follow} disabled={busy} className={`${data.is_following ? "btn-ghost !border-[#CCFF00] !text-[#CCFF00]" : "btn-lime"} !py-2 !px-4 text-xs flex items-center gap-2`}>
                {data.is_following ? <UserCheck size={13} /> : <UserPlus size={13} />} {data.is_following ? "Following" : "Follow"}
              </button>
            )}
            {host.is_artist && <Link to={`/artist/${host.id}`} data-testid="host-studio-link" className="btn-ghost !py-2 !px-4 text-xs flex items-center gap-2"><Palette size={13} /> Studio</Link>}
            <button data-testid="host-share-btn" onClick={share} className="btn-ghost !py-2 !px-3 text-xs"><Share2 size={13} /></button>
            <ReportButton targetType="user" targetId={host.id} ownerId={host.id} compact />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6" data-testid="host-stats">
        {[["Events hosted", stats.events], ["Upcoming", stats.upcoming], ["Total attendees", stats.attendees], ["Followers", stats.followers]].map(([l, v]) => (
          <div key={l} className="border border-white/8 rounded-sm p-4"><div className="label-caps text-zinc-500 text-[10px]">{l}</div><div className="font-anton text-3xl mt-1">{v}</div></div>
        ))}
      </div>
      {stats.categories?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-4">{stats.categories.map((c) => { const m = catMeta(c); return <span key={c} className="label-caps text-[10px] px-2 py-1 rounded-full border" style={{ borderColor: `${m.color}66`, color: m.color }}>{m.label}</span>; })}</div>
      )}

      <div className="flex gap-2 mt-10 mb-5 border-b border-white/8">
        {[["upcoming", `Upcoming (${upcoming.length})`], ["past", `Past (${past.length})`]].map(([k, l]) => (
          <button key={k} data-testid={`host-tab-${k}`} onClick={() => setTab(k)} className={`label-caps text-xs px-4 py-3 border-b-2 -mb-px ${tab === k ? "border-[#CCFF00] text-[#CCFF00]" : "border-transparent text-zinc-500"}`}>{l}</button>
        ))}
      </div>
      {list.length === 0 ? (
        <div className="border border-dashed border-white/10 rounded-sm p-16 text-center"><Calendar size={26} className="mx-auto text-zinc-600 mb-3" /><div className="label-caps text-zinc-500">No {tab} events</div></div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid={`host-events-${tab}`}>
          {list.map((e) => <EventCard key={e.id} event={e} catMeta={catMeta} user={user} onChange={load} />)}
        </div>
      )}
      <div className="text-xs text-zinc-600 mt-8 flex items-center gap-1"><Users size={11} /> Follow a host to get their events in your "Picked for you" rail.</div>
    </div>
  );
}
