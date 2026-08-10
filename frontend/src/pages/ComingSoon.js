import React from "react";
import { Link } from "react-router-dom";

/**
 * Reusable "Coming Soon" premium page for stubbed v2 features
 * — Auctions, Commissions, Events, Rankings, Studio customization.
 */
export default function ComingSoon({ title, tagline, description, accent = "#CCFF00", icon }) {
  return (
    <div data-testid={`coming-soon-${title.toLowerCase().replace(/\s/g, "-")}`}
      className="relative max-w-[1200px] mx-auto px-6 md:px-12 pt-32 pb-40 min-h-[80vh] flex flex-col items-start justify-center">
      <div className="relative">
        <div className="label-caps mb-6" style={{ color: accent }}>Coming Soon · v2</div>
        <h1 className="font-anton text-7xl md:text-9xl leading-[0.85] uppercase" style={{ color: "#FFF" }}>
          {title}
        </h1>
        {tagline && <div className="font-unbounded text-xl md:text-2xl mt-6 max-w-2xl text-white">{tagline}</div>}
        <p className="text-zinc-400 mt-8 max-w-2xl leading-relaxed">{description}</p>

        <div className="mt-12 flex flex-wrap gap-4">
          <Link to="/explore" data-testid="cs-explore" className="btn-lime">Explore Now</Link>
          <Link to="/" data-testid="cs-home" className="btn-ghost">Back to Home</Link>
        </div>
      </div>

      {/* decorative floating chip */}
      <div className="absolute right-6 md:right-12 top-32 rotate-6 pointer-events-none">
        <div className="glass-card px-6 py-3 flex items-center gap-3 rounded-sm">
          {icon}
          <div>
            <div className="label-caps" style={{ color: accent }}>Feature drop</div>
            <div className="font-unbounded text-sm">Notify me on launch</div>
          </div>
        </div>
      </div>
    </div>
  );
}
