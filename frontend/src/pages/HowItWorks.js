import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Search, ShieldCheck, PackageCheck, Upload, Truck, Wallet, Gavel, Ticket, Brush, ChevronDown } from "lucide-react";

const Step = ({ n, icon: Icon, title, body }) => (
  <div className="relative glass-card rounded-sm p-6 border border-white/8" data-testid={`hiw-step-${n}`}>
    <div className="flex items-center gap-3">
      <span className="font-anton text-4xl text-[#CCFF00]/40 leading-none">{String(n).padStart(2, "0")}</span>
      <span className="w-9 h-9 rounded-full bg-[#CCFF00]/10 text-[#CCFF00] flex items-center justify-center"><Icon size={16} /></span>
    </div>
    <div className="font-unbounded font-semibold mt-4">{title}</div>
    <p className="text-sm text-zinc-400 mt-2 leading-relaxed">{body}</p>
  </div>
);

const FAQ = ({ q, a, id }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-white/8">
      <button data-testid={`faq-${id}`} onClick={() => setOpen(!open)} className="w-full flex items-center justify-between py-4 text-left">
        <span className="font-unbounded text-sm font-semibold">{q}</span>
        <ChevronDown size={16} className={`text-zinc-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <p className="text-sm text-zinc-400 pb-4 leading-relaxed">{a}</p>}
    </div>
  );
};

export default function HowItWorks() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/settings").then((r) => setS(r.data)).catch(() => {}); }, []);
  const pct = Number(s?.commission_percent ?? 4);
  const proc = Number(s?.processing_percent ?? 2.9);
  const fixed = Number(s?.processing_fixed ?? 0.3);
  const gross = 100;
  const fee = +(gross * pct / 100).toFixed(2);
  const stripe = +(gross * proc / 100 + fixed).toFixed(2);
  const net = +(gross - fee - stripe).toFixed(2);

  return (
    <div data-testid="how-it-works-page" className="max-w-6xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]">How it works</div>
      <h1 className="font-anton text-5xl sm:text-6xl lg:text-7xl uppercase mt-4 leading-none">Real art. Real artists.<br />Money that moves when the art does.</h1>
      <p className="text-base md:text-lg text-zinc-400 mt-6 max-w-2xl">Art Core is a marketplace built only for artists. No galleries taking half. No algorithms burying you. Just collectors, artists, and a payment system that protects both.</p>

      <section className="mt-20" data-testid="hiw-collectors">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <h2 className="font-anton text-3xl md:text-4xl uppercase">For collectors</h2>
          <Link to="/explore" className="label-caps text-[#CCFF00] hover:underline">Start exploring →</Link>
        </div>
        <div className="grid md:grid-cols-3 gap-4 mt-8">
          <Step n={1} icon={Search} title="Find a piece you love" body="Browse the Marketplace, follow artists, bid in live auctions, make an offer, or commission something made just for you." />
          <Step n={2} icon={ShieldCheck} title="Pay — we hold it" body="Checkout is by card through Stripe. Art Core holds your payment. The artist doesn't get paid yet." />
          <Step n={3} icon={PackageCheck} title="Confirm it arrived" body="The artist ships with tracking. When it shows delivered, you tap “I received it” (or “I didn't”). Only then is the artist paid. Every original comes with a certificate of authenticity." />
        </div>
      </section>

      <section className="mt-20" data-testid="hiw-artists">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <h2 className="font-anton text-3xl md:text-4xl uppercase">For artists</h2>
          <Link to="/register?role=artist" className="label-caps text-[#CCFF00] hover:underline">Open your studio →</Link>
        </div>
        <div className="grid md:grid-cols-3 gap-4 mt-8">
          <Step n={1} icon={Upload} title="Build your studio" body="Your own themed storefront — pick a look, upload work, write your story, publish. Takes 10 minutes." />
          <Step n={2} icon={Truck} title="Sell and ship" body="A collector buys. You pack it, enter the tracking number (required), and you're done. We prompt the buyer to confirm delivery." />
          <Step n={3} icon={Wallet} title="Get paid" body="Payout lands in your bank via Stripe 2 days after the buyer confirms (same day for Pro). If they never respond, it auto-releases after 3 days." />
        </div>
      </section>

      <section className="mt-20 grid lg:grid-cols-2 gap-8" data-testid="hiw-fees">
        <div>
          <h2 className="font-anton text-3xl md:text-4xl uppercase">The fee, in plain numbers</h2>
          <p className="text-sm text-zinc-400 mt-4 leading-relaxed">Art Core takes <span className="text-white font-semibold">{pct}%</span>. Card processing ({proc}% + ${fixed.toFixed(2)}) is charged at cost — we don't mark it up. Founding Artists lock their rate for life, and every new artist gets their first {s?.waiver_days ?? 30} days (or {s?.waiver_max_sales ?? 5} sales) at 0%.</p>
          <p className="text-sm text-zinc-400 mt-3">Compare: galleries take 40–50%. Etsy takes ~9.5% plus listing fees.</p>
        </div>
        <div className="glass-card rounded-sm p-6 border border-[#CCFF00]/30">
          <div className="label-caps text-zinc-500">A ${gross} sale</div>
          <div className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-zinc-400">Collector pays</span><span className="font-semibold">${gross.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Art Core fee ({pct}%)</span><span className="text-[#FF4D4D]">− ${fee.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Card processing</span><span className="text-[#FF4D4D]">− ${stripe.toFixed(2)}</span></div>
            <div className="flex justify-between border-t border-white/10 pt-3 mt-3"><span className="font-unbounded font-semibold">Artist keeps</span><span className="font-anton text-3xl text-[#CCFF00]" data-testid="hiw-net">${net.toFixed(2)}</span></div>
          </div>
        </div>
      </section>

      <section className="mt-20" data-testid="hiw-more">
        <h2 className="font-anton text-3xl md:text-4xl uppercase">More than a shop</h2>
        <div className="grid md:grid-cols-3 gap-4 mt-8">
          <Step n="" icon={Gavel} title="Live auctions" body="Artists set a start price and a clock. Bids update live. Set a max bid and we bid for you, eBay-style." />
          <Step n="" icon={Ticket} title="Events & tickets" body="Openings, live-painting nights, workshops, pop-ups — find them near you, grab a QR ticket, show it at the door." />
          <Step n="" icon={Brush} title="Commissions & flips" body="Ask any artist for a custom piece — or send a photo of tired furniture and get it flipped. Deposit held in escrow until you approve." />
        </div>
      </section>

      <section className="mt-20 max-w-3xl" data-testid="hiw-faq">
        <h2 className="font-anton text-3xl md:text-4xl uppercase mb-4">Questions people actually ask</h2>
        <FAQ id="not-arrive" q="What if my piece never arrives?" a="Tap “I did not receive it” on the prompt. The artist's payout is frozen immediately, a case opens with the tracking proof attached, and Art Core reviews it. If the carrier can't show delivery to your address, you're refunded in full." />
        <FAQ id="damaged" q="It arrived damaged." a="Open a dispute from the order page within 3 days with photos. Outcomes are full refund, partial refund, or a return — decided by Art Core, not the seller." />
        <FAQ id="when-paid" q="Artists: when exactly do I get paid?" a="Two days after the buyer confirms delivery (same day on Art Core Pro). If the buyer ignores the prompt, funds release automatically 3 days after the carrier marks it delivered. Brand-new Stripe accounts may see a one-time 7-day hold on the first payout — that's Stripe, not us." />
        <FAQ id="tracking" q="Do I have to use tracking?" a="Yes. You can't mark an order shipped without a carrier and tracking number. It's what protects you from “I never got it” claims." />
        <FAQ id="prohibited" q="What can't be sold or shipped?" a="Only the artwork in the listing. Anything else in the package — controlled substances, weapons, counterfeits, anything illegal — is the sole responsibility of whoever shipped it, and gets the account terminated. See our Terms." />
        <FAQ id="pro" q="What's Art Core Pro?" a="$12/month: premium studio themes, boosted placement in the Marketplace, faster payouts, and a Pro badge. Founding Artists get it half price forever." />
      </section>

      <div className="mt-20 glass-card rounded-sm p-8 md:p-12 border border-white/8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <div className="font-anton text-3xl md:text-4xl uppercase">Ready?</div>
          <div className="text-sm text-zinc-400 mt-2">Collectors browse free. Artists open a studio in 10 minutes.</div>
        </div>
        <div className="flex gap-3 flex-wrap">
          <Link to="/register?role=artist" className="btn-lime" data-testid="hiw-cta-artist">Open a studio</Link>
          <Link to="/explore" className="btn-ghost" data-testid="hiw-cta-explore">Explore art</Link>
        </div>
      </div>
    </div>
  );
}
