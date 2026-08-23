import React from "react";
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div data-testid="not-found" className="max-w-2xl mx-auto px-6 pt-32 pb-32 text-center">
      <div className="label-caps text-[#7C3AED]">404</div>
      <h1 className="font-anton text-7xl md:text-9xl uppercase mt-4 leading-none">Off canvas.</h1>
      <p className="text-zinc-400 mt-8">This piece doesn't hang here. Try the gallery or the roster.</p>
      <div className="flex flex-wrap gap-3 justify-center mt-10">
        <Link to="/" data-testid="nf-home" className="btn-lime">Back Home</Link>
        <Link to="/explore" data-testid="nf-explore" className="btn-ghost">Explore</Link>
        <Link to="/artists" data-testid="nf-artists" className="btn-ghost">Artists</Link>
      </div>
    </div>
  );
}
