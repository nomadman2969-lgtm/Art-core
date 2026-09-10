import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, thumbUrl } from "../api";
import { useAuth } from "../context/AuthContext";
import { ArtCard } from "../components/ArtCard";
import { toast } from "sonner";
import { UserPlus, UserCheck, MessageCircle, MapPin, Palette } from "lucide-react";
import { RankBadge } from "./Rankings";

const resolveImg = (p) => thumbUrl(p, 480);

export function ArtistsList() {
  const [artists, setArtists] = useState([]);
  useEffect(() => { api.get("/artists").then((r) => setArtists(r.data)); }, []);
  return (
    <div data-testid="artists-list" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="mb-12">
        <div className="label-caps text-[#CCFF00]">The Roster</div>
        <h1 className="font-anton text-6xl md:text-9xl uppercase mt-4 leading-[0.85]">Artists</h1>
      </div>
      {artists.length === 0 ? (
        <div className="text-zinc-500 py-24 text-center label-caps border border-dashed border-white/10 rounded-sm">No artists yet.</div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {artists.map((a) => (
            <Link key={a.id} to={`/artist/${a.id}`} data-testid={`artist-card-${a.id}`}
              className="glass-card p-8 hover-lift-card group rounded-sm">
              <div className="flex items-center gap-4 mb-4">
                <div className="avatar-ring w-16 h-16">
                  <div className="bg-[#0A0A0C] rounded-full w-full h-full flex items-center justify-center font-anton text-2xl uppercase">
                    {a.name?.[0]}
                  </div>
                </div>
                <div>
                  <div className="font-unbounded font-semibold text-lg group-hover:text-[#CCFF00] transition-colors">{a.name}</div>
                  <div className="label-caps mt-1">{a.artwork_count} works</div>
                </div>
              </div>
              <div className="text-zinc-400 text-sm line-clamp-3">{a.bio || "Independent artist."}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function ArtistPortfolio() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [artist, setArtist] = useState(null);
  const [social, setSocial] = useState(null);
  const [rank, setRank] = useState(null);
  const loadAll = () => {
    api.get(`/artists/${id}`).then((r) => setArtist(r.data));
    api.get(`/users/${id}/social`).then((r) => setSocial(r.data));
    api.get(`/rankings/${id}`).then((r) => setRank(r.data)).catch(() => {});
  };
  useEffect(loadAll, [id]);

  const toggleFollow = async () => {
    if (!user) { toast("Sign in to follow"); return; }
    try {
      if (social?.is_following) { await api.delete(`/users/${id}/follow`); }
      else { await api.post(`/users/${id}/follow`); }
      loadAll();
    } catch { toast.error("Try again"); }
  };

  if (!artist) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;

  return (
    <div data-testid="artist-portfolio" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-12 pb-32">
      {/* Banner */}
      <div className="relative aspect-[4/1] overflow-hidden bg-[#121214] border border-white/8 rounded-sm">
        {artist.cover_image ? (
          <img src={resolveImg(artist.cover_image)} className="w-full h-full object-cover" alt="cover" />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-[#121214] via-[#7C3AED]/10 to-[#121214]" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0C]/80 to-transparent" />
      </div>

      <div className="grid md:grid-cols-12 gap-8 -mt-16 relative z-10 mb-16">
        <div className="md:col-span-4">
          <div className="avatar-ring w-32 h-32">
            <div className="bg-[#0A0A0C] rounded-full w-full h-full flex items-center justify-center font-anton text-5xl uppercase">
              {artist.name?.[0]}
            </div>
          </div>
          <h1 className="font-anton text-5xl md:text-6xl uppercase mt-6 leading-[0.95]">{artist.name}</h1>
          <div className="flex items-center gap-2 mt-2 label-caps">
            <MapPin size={12} /> Brooklyn, NY
          </div>
          {rank && (
            <div className="mt-4 flex items-center gap-3">
              <RankBadge tier={rank.tier} color={rank.tier_color} />
              <div className="label-caps">
                <span className="text-[#CCFF00]">{rank.score}</span> pts · #{rank.position} of {rank.total_artists}
              </div>
            </div>
          )}
          <div className="flex flex-wrap gap-3 mt-6">
            {user?.id !== artist.id && (
              <button data-testid="follow-btn" onClick={toggleFollow}
                className={social?.is_following ? "btn-ghost" : "btn-lime"}>
                {social?.is_following ? <><UserCheck size={14} className="mr-2" />Following</> : <><UserPlus size={14} className="mr-2" />Follow</>}
              </button>
            )}
            {user && user.id !== artist.id && (
              <button data-testid="message-btn" onClick={() => nav(`/messages/${artist.id}`)} className="btn-ghost">
                <MessageCircle size={14} className="mr-2" /> Message
              </button>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3 mt-8">
            <StatMini label="Works" value={artist.artworks.length} />
            <StatMini label="Followers" value={social?.followers ?? 0} />
            <StatMini label="Following" value={social?.following ?? 0} />
          </div>
        </div>
        <div className="md:col-span-8 md:pt-24">
          <div className="label-caps text-[#CCFF00]">Bio</div>
          <p className="text-zinc-300 leading-relaxed text-lg whitespace-pre-wrap mt-4">{artist.bio || "This artist keeps their story on the canvas."}</p>
        </div>
      </div>

      <div className="label-caps mb-6">Portfolio ({artist.artworks.length})</div>
      {artist.artworks.length === 0 ? (
        <div className="text-zinc-500 py-24 text-center label-caps border border-dashed border-white/10 rounded-sm">No pieces yet.</div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {artist.artworks.map((a, i) => <ArtCard key={a.id} art={{ ...a, artist }} tall={i % 5 === 0} />)}
        </div>
      )}
    </div>
  );
}

function StatMini({ label, value }) {
  return (
    <div className="glass-card p-3 text-center rounded-sm">
      <div className="font-anton text-2xl">{value}</div>
      <div className="label-caps mt-0.5 !text-[9px]">{label}</div>
    </div>
  );
}
