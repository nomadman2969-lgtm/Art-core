import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { ArtCard } from "../components/ArtCard";

export default function Search() {
  const [params] = useSearchParams();
  const q = params.get("q") || "";
  const [data, setData] = useState({ artworks: [], artists: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!q) { setLoading(false); return; }
    setLoading(true);
    api.get(`/search?q=${encodeURIComponent(q)}`).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [q]);

  return (
    <div data-testid="search-page" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]">Search</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4">"{q}"</h1>
      {loading ? <div className="text-zinc-500 py-24 text-center label-caps">Searching...</div> : (
        <>
          <div className="mt-12">
            <div className="label-caps mb-6">Artists ({data.artists.length})</div>
            {data.artists.length === 0 ? <div className="text-zinc-500 label-caps py-4">No artists found.</div> : (
              <div className="grid md:grid-cols-3 gap-4">
                {data.artists.map((a) => (
                  <Link key={a.id} to={`/artist/${a.id}`} data-testid={`search-artist-${a.id}`}
                    className="glass-card p-6 hover-lift-card rounded-sm">
                    <div className="font-unbounded font-semibold text-lg">{a.name}</div>
                    <div className="text-xs text-zinc-500 mt-1 line-clamp-2">{a.bio || "Independent artist."}</div>
                  </Link>
                ))}
              </div>
            )}
          </div>
          <div className="mt-16">
            <div className="label-caps mb-6">Artworks ({data.artworks.length})</div>
            {data.artworks.length === 0 ? <div className="text-zinc-500 label-caps py-4">No artworks found.</div> : (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {data.artworks.map((a) => <ArtCard key={a.id} art={a} />)}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
