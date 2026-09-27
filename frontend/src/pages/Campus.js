import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, fileUrl } from "../api";
import { useAuth } from "../context/AuthContext";
import { ArtCard } from "../components/ArtCard";
import { ArtistBadges } from "../components/Badges";
import { SchoolPicker } from "../components/SchoolPicker";
import { EmptyState } from "../components/EmptyState";
import { toast } from "sonner";
import { GraduationCap, MapPin, Share2, Trophy, Users, Calendar, ArrowRight, Sparkles } from "lucide-react";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export function CampusDirectory() {
  const [items, setItems] = useState(null);
  const nav = useNavigate();
  const { user } = useAuth();
  useEffect(() => { api.get("/campus").then((r) => setItems(r.data)).catch(() => setItems([])); }, []);
  return (
    <div data-testid="campus-directory" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="grid lg:grid-cols-[1fr_420px] gap-10 items-end mb-14">
        <div>
          <div className="label-caps text-[#CCFF00] flex items-center gap-2"><GraduationCap size={14} /> Campus</div>
          <h1 className="font-anton text-6xl md:text-9xl uppercase mt-4 leading-[0.85]">Art Schools<br /><span className="text-zinc-500">on Art Core</span></h1>
          <p className="text-zinc-400 mt-6 max-w-xl leading-relaxed">Every school gets a page the moment one of its artists tags it — studios, fresh work, campus events and a leaderboard. Find yours or start it.</p>
        </div>
        <div className="glass-card p-6 rounded-sm">
          <div className="label-caps mb-3">Find a school</div>
          <SchoolPicker value={null} allowCreate={false} testid="campus-search" placeholder="RISD, Central Saint Martins, SCAD…" onChange={(c) => c?.slug && nav(`/campus/${c.slug}`)} />
          {user?.role === "artist" && <Link to="/studio?tab=story" data-testid="campus-tag-mine" className="mt-4 inline-flex items-center gap-2 label-caps text-[#CCFF00] hover:text-white">Tag your school in Studio <ArrowRight size={12} /></Link>}
          {!user && <Link to="/register?role=artist" data-testid="campus-join-cta" className="mt-4 inline-flex items-center gap-2 label-caps text-[#CCFF00] hover:text-white">Join as an artist to start your campus <ArrowRight size={12} /></Link>}
        </div>
      </div>
      {items === null ? <div className="py-24 text-center label-caps text-zinc-500">Loading…</div> :
        items.length === 0 ? (
          <EmptyState icon="compass" title="No campus pages yet" body="The first artist to tag their school starts its page. Could be you." cta={user?.role === "artist" ? "Tag my school" : "Join as an artist"} to={user?.role === "artist" ? "/studio?tab=story" : "/register?role=artist"} testId="campus-empty" />
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {items.map((c, i) => (
              <Link key={c.id} to={`/campus/${c.slug}`} data-testid={`campus-card-${c.slug}`} className="glass-card p-6 rounded-sm hover-lift-card group relative overflow-hidden">
                {c.featured && <div className="absolute top-3 right-3 badge-lime">Featured</div>}
                <div className="font-anton text-4xl text-zinc-700 group-hover:text-[#CCFF00]/40 transition-colors">{String(i + 1).padStart(2, "0")}</div>
                <div className="font-unbounded font-semibold text-lg mt-2 leading-snug group-hover:text-[#CCFF00] transition-colors">{c.name}</div>
                <div className="text-xs text-zinc-500 mt-1 flex items-center gap-1"><MapPin size={11} /> {[c.city, c.country].filter(Boolean).join(" · ") || "—"}</div>
                <div className="label-caps mt-4 text-zinc-400">{c.artist_count} artist{c.artist_count === 1 ? "" : "s"}</div>
              </Link>
            ))}
          </div>
        )}
    </div>
  );
}

export default function CampusPage() {
  const { slug } = useParams();
  const nav = useNavigate();
  const { user, refresh } = useAuth();
  const [data, setData] = useState(null);
  const [missing, setMissing] = useState(false);
  const [joining, setJoining] = useState(false);

  const load = () => api.get(`/campus/${slug}`).then((r) => { setData(r.data); setMissing(false); }).catch(() => setMissing(true));
  useEffect(() => { load(); }, [slug]);

  if (missing) return <div className="pt-24"><EmptyState icon="compass" title="Campus not found" body="This school hasn't been added yet." cta="Browse campuses" to="/campus" testId="campus-missing" /></div>;
  if (!data) return <div className="py-32 text-center label-caps text-zinc-500">Opening campus…</div>;
  const { campus, stats, artists, artworks, events, leaderboard } = data;
  const isMember = user?.campus?.id === campus.id;

  const join = async () => {
    if (!user) { nav(`/register?role=artist&next=/campus/${slug}`); return; }
    if (user.role !== "artist") { toast("Only artists can join a campus"); return; }
    setJoining(true);
    try { await api.post("/campus/me", { campus_id: campus.id }); await refresh?.(); toast.success(`You're on the ${campus.name} page`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setJoining(false);
  };
  const share = () => {
    const u = `${window.location.origin}/campus/${campus.slug}`;
    if (navigator.share) navigator.share({ title: `${campus.name} · Art Core`, url: u }).catch(() => {});
    else { navigator.clipboard.writeText(u); toast.success("Link copied"); }
  };

  return (
    <div data-testid="campus-page" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-32">
      {campus.status === "pending" && <div data-testid="campus-pending-banner" className="mb-6 border-l-4 border-[#F5A623] bg-[#F5A623]/10 p-4 text-sm text-zinc-200">This school was just added by an artist and is awaiting moderator approval. The page works already.</div>}
      <div className="flex flex-wrap items-end justify-between gap-8">
        <div className="max-w-3xl">
          <div className="label-caps text-[#CCFF00] flex items-center gap-2"><GraduationCap size={14} /> Campus</div>
          <h1 data-testid="campus-name" className="font-anton text-5xl md:text-8xl uppercase mt-4 leading-[0.9] tracking-tight">{campus.name}</h1>
          <div className="mt-4 flex flex-wrap items-center gap-4 label-caps">
            {(campus.city || campus.country) && <span className="flex items-center gap-1"><MapPin size={12} /> {[campus.city, campus.country].filter(Boolean).join(" · ")}</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          {!isMember && (user?.role !== "buyer") && (
            <button data-testid="campus-join" onClick={join} disabled={joining} className="btn-lime"><Sparkles size={14} className="mr-2" /> {user ? "I go here" : "Join as an artist"}</button>
          )}
          {isMember && <Link to="/studio?tab=story" data-testid="campus-member-chip" className="btn-ghost">✓ Your campus</Link>}
          <button data-testid="campus-share" onClick={share} className="btn-ghost"><Share2 size={14} className="mr-2" /> Share</button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-12" data-testid="campus-stats">
        <Stat label="Artists" value={stats.artists} />
        <Stat label="Works for sale" value={stats.artworks_live} />
        <Stat label="Sales" value={stats.sales} />
        <Stat label="Upcoming events" value={stats.events_upcoming} />
      </div>

      {artists.length === 0 ? (
        <div className="mt-20">
          <EmptyState icon="palette" title="Nobody from here yet" body="Be the first artist to represent this school. Tag it and your studio shows up here instantly." cta={user?.role === "buyer" ? null : (user ? "I go here" : "Join as an artist")} onClick={join} testId="campus-no-artists" />
        </div>
      ) : (
        <>
          <Section title="Artists" icon={<Users size={14} />} count={artists.length}>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {artists.map((a) => (
                <Link key={a.id} to={`/artist/${a.id}`} data-testid={`campus-artist-${a.id}`} className="glass-card p-5 rounded-sm hover-lift-card group flex gap-4 items-center min-w-0">
                  <div className="avatar-ring w-14 h-14 shrink-0">
                    {a.avatar ? <img src={resolveImg(a.avatar)} alt="" className="w-full h-full object-cover rounded-full" /> :
                      <div className="bg-[#0A0A0C] rounded-full w-full h-full flex items-center justify-center font-anton text-xl uppercase">{a.name?.[0]}</div>}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-unbounded font-semibold group-hover:text-[#CCFF00] transition-colors flex items-center gap-x-1.5 gap-y-1 flex-wrap min-w-0"><span className="min-w-0 break-words">{a.name}</span><span className="shrink-0"><ArtistBadges artist={a} /></span></div>
                    <div className="text-[11px] text-zinc-500 mt-1">{a.works} works · {a.followers} followers{a.sales ? ` · ${a.sales} sold` : ""}</div>
                  </div>
                </Link>
              ))}
            </div>
          </Section>

          {(leaderboard.sales.length > 0 || leaderboard.followers.length > 0) && (
            <Section title="Leaderboard" icon={<Trophy size={14} />}>
              <div className="grid md:grid-cols-2 gap-4">
                <Board title="Top sellers" rows={leaderboard.sales} metric={(a) => `${a.sales} sold`} testid="board-sales" />
                <Board title="Most followed" rows={leaderboard.followers} metric={(a) => `${a.followers} followers`} testid="board-followers" />
              </div>
            </Section>
          )}

          <Section title="Fresh work" icon={<Sparkles size={14} />} count={artworks.length}>
            {artworks.length === 0 ? <div className="text-zinc-500 label-caps">Nothing listed yet.</div> : (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {artworks.map((a, i) => <ArtCard key={a.id} art={a} tall={i % 5 === 0} />)}
              </div>
            )}
          </Section>

          <Section title="Campus events" icon={<Calendar size={14} />} count={events.length}>
            {events.length === 0 ? <div className="text-zinc-500 label-caps">No upcoming events. Artists here can host one from the Events page.</div> : (
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {events.map((e) => (
                  <Link key={e.id} to={`/events/${e.id}`} data-testid={`campus-event-${e.id}`} className="glass-card rounded-sm overflow-hidden hover-lift-card">
                    <div className="aspect-video bg-black">{e.cover_image && <img src={resolveImg(e.cover_image)} alt="" className="w-full h-full object-cover" />}</div>
                    <div className="p-4">
                      <div className="label-caps text-[#CCFF00]">{new Date(e.start_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })} · {e.category?.replace(/_/g, " ")}</div>
                      <div className="font-unbounded font-semibold mt-1 truncate">{e.title}</div>
                      <div className="text-xs text-zinc-500 mt-1 truncate flex items-center gap-1"><MapPin size={11} /> {[e.venue, e.location?.city].filter(Boolean).join(" · ") || "TBA"}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Section>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return <div className="glass-card p-5 rounded-sm"><div className="label-caps">{label}</div><div className="font-anton text-4xl mt-2 text-[#CCFF00]">{value}</div></div>;
}
function Section({ title, icon, count, children }) {
  return (
    <div className="mt-20">
      <div className="mb-8 flex items-baseline gap-4">
        <div className="w-2 h-8 bg-[#CCFF00]" />
        <h2 className="font-anton text-3xl md:text-5xl uppercase">{title}</h2>
        {count != null && <span className="label-caps text-zinc-500">{count}</span>}
      </div>
      {children}
    </div>
  );
}
function Board({ title, rows, metric, testid }) {
  if (!rows.length) return null;
  return (
    <div className="glass-card p-5 rounded-sm" data-testid={testid}>
      <div className="label-caps mb-4">{title}</div>
      <div className="divide-y divide-white/8">
        {rows.map((a, i) => (
          <Link key={a.id} to={`/artist/${a.id}`} className="flex items-center gap-4 py-3 hover:text-[#CCFF00]">
            <div className="font-anton text-2xl w-8 text-zinc-500">{i + 1}</div>
            <div className="flex-1 font-unbounded text-sm truncate">{a.name}</div>
            <div className="label-caps text-zinc-400">{metric(a)}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
