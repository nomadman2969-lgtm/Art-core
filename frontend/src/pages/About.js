import React from "react";
import { Link } from "react-router-dom";

const FOUNDER_IMG = "https://images.unsplash.com/photo-1656657447800-ed397d4128b5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NDh8MHwxfHNlYXJjaHwyfHxicm9va2x5biUyMGFydGlzdCUyMGluJTIwc3R1ZGlvfGVufDB8fHx8MTc4NTQ1MTg2OHww&ixlib=rb-4.1.0&q=85";
const GALLERY_IMG = "https://images.unsplash.com/photo-1518998053901-5348d3961a04?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NTZ8MHwxfHNlYXJjaHwyfHxtb2Rlcm4lMjBhcnQlMjBnYWxsZXJ5JTIwZXhoaWJpdGlvbnxlbnwwfHx8fDE3ODU0NTE4Njh8MA&ixlib=rb-4.1.0&q=85";
const CATS_IMG = "https://images.unsplash.com/photo-1784202318366-35fd82271209?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzZ8MHwxfHNlYXJjaHwyfHx0d28lMjBjYXRzJTIwc2xlZXBpbmclMjBvbiUyMHJ1Z3xlbnwwfHx8fDE3ODU0NTE4Njh8MA&ixlib=rb-4.1.0&q=85";

export default function About() {
  return (
    <div data-testid="about-page" className="max-w-[1200px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#FF1493]">The Monster Story</div>
      <h1 className="font-serif text-6xl md:text-8xl mt-4 tracking-tighter leading-[0.9]">A small room<br /><span className="italic">full of loud</span> paint.</h1>

      <div className="grid md:grid-cols-12 gap-12 mt-20">
        <div className="md:col-span-5">
          <img src={FOUNDER_IMG} className="w-full aspect-[4/5] object-cover" alt="Monster" />
        </div>
        <div className="md:col-span-7 space-y-6 text-lg leading-relaxed text-zinc-300">
          <p>House of Monster started in a walk-up in Brooklyn. Between a bodega and a landmarked church. Between two cats that don't get along and a rent bill that gets bigger every year.</p>
          <p>I paint abstracts. Big, ugly, honest ones. Somewhere along the way I realized every good painter I knew was funneling their work into feeds that flattened it. So I opened a room.</p>
          <p>This is the room. Every piece here got a look — a real look — before it went up. If it's live, it's because Monster liked it.</p>
          <p className="text-[#FFD700] font-serif text-2xl">— Monster</p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6 mt-24">
        <img src={CATS_IMG} className="w-full aspect-square object-cover" alt="two cats" />
        <img src={GALLERY_IMG} className="w-full aspect-square object-cover" alt="gallery" />
      </div>

      <div className="text-center mt-24">
        <h2 className="font-serif text-4xl md:text-6xl">Come hang your work.</h2>
        <Link to="/register?role=artist" className="btn-monster mt-8 inline-flex">Apply to Sell</Link>
      </div>
    </div>
  );
}
