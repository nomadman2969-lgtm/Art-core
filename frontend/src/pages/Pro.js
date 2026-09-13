import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Crown, Check, Loader2, Sparkles, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { api, ORIGIN } from "../api";
import { useAuth } from "../context/AuthContext";

export default function Pro() {
  const { user, refresh } = useAuth();
  const [plans, setPlans] = useState(null);
  const [status, setStatus] = useState(null);
  const [interval, setInterval_] = useState("month");
  const [busy, setBusy] = useState(false);

  const load = () => {
    api.get("/pro/plans").then((r) => setPlans(r.data)).catch(() => {});
    if (user) api.get("/pro/status").then((r) => setStatus(r.data)).catch(() => {});
  };
  useEffect(load, [user?.id]);

  const subscribe = async () => {
    if (!user) return toast("Sign in as an artist to go Pro");
    setBusy(true);
    try { const r = await api.post("/pro/checkout", { interval, origin_url: ORIGIN }); window.location.href = r.data.checkout_url; }
    catch (e) { toast.error(e?.response?.data?.detail || "Couldn't start checkout"); setBusy(false); }
  };
  const act = async (path, msg) => {
    setBusy(true);
    try { await api.post(`/pro/${path}`, {}); toast.success(msg); load(); refresh?.(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Something went wrong"); }
    finally { setBusy(false); }
  };
  const portal = async () => {
    try { const r = await api.post("/pro/portal", { origin_url: ORIGIN }); window.location.href = r.data.url; }
    catch (e) { toast.error(e?.response?.data?.detail || "Billing portal unavailable"); }
  };

  if (!plans) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;
  const price = plans.prices[interval];
  const founder = plans.founder_discount;
  const shown = founder ? price.founder_amount : price.amount;
  const active = status?.active;

  return (
    <div data-testid="pro-page" className="max-w-5xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#C4B5FD] flex items-center gap-2"><Crown size={12} /> Art Core Pro</div>
      <h1 className="font-anton text-4xl sm:text-5xl lg:text-7xl uppercase mt-3 leading-[0.9]">More eyes.<br />Faster money.<br /><span className="text-[#C4B5FD]">Your look.</span></h1>
      <p className="text-zinc-400 mt-6 max-w-xl text-sm md:text-base">Pro is optional and never touches your commission — your 4% stays exactly where it is. It's for artists who want to move more work, faster.</p>

      <div className="grid lg:grid-cols-[1.2fr_1fr] gap-8 mt-14 items-start">
        <div className="grid sm:grid-cols-2 gap-4">
          {plans.perks.map((p) => (
            <div key={p.title} className="glass-card rounded-sm p-6" data-testid="pro-perk">
              <Check size={16} className="text-[#C4B5FD]" />
              <div className="font-unbounded text-sm mt-4">{p.title}</div>
              <div className="text-xs text-zinc-500 mt-2">{p.body}</div>
            </div>
          ))}
        </div>

        <div className="glass-card rounded-sm p-8 border border-[#7C3AED]/40 relative overflow-hidden" data-testid="pro-plan-card">
          <div className="absolute -top-16 -right-16 w-48 h-48 bg-[#7C3AED] opacity-20 blur-3xl rounded-full" />
          {active ? (
            <div className="relative" data-testid="pro-active-panel">
              <div className="label-caps text-[#C4B5FD]">You're on Pro</div>
              <div className="font-anton text-4xl uppercase mt-2">Active</div>
              <div className="text-xs text-zinc-400 mt-3">
                ${status.amount}/{status.interval}{status.discount ? " · founder price" : ""}
                {status.current_period_end && <> · {status.cancel_at_period_end ? "ends" : "renews"} {new Date(status.current_period_end * 1000).toLocaleDateString()}</>}
              </div>
              <div className="flex flex-wrap gap-3 mt-8">
                {status.cancel_at_period_end
                  ? <button data-testid="pro-resume-btn" onClick={() => act("resume", "Pro will keep renewing")} disabled={busy} className="btn-lime">Keep Pro</button>
                  : <button data-testid="pro-cancel-btn" onClick={() => act("cancel", "Pro ends at the end of this period")} disabled={busy} className="btn-ghost">Cancel at period end</button>}
                <button data-testid="pro-portal-btn" onClick={portal} className="btn-ghost flex items-center gap-1">Billing <ExternalLink size={12} /></button>
              </div>
              <Link to="/studio" className="label-caps text-zinc-400 hover:text-white mt-6 inline-block">Back to studio →</Link>
            </div>
          ) : (
            <div className="relative">
              <div className="flex gap-2" data-testid="pro-interval-toggle">
                {[["month", "Monthly"], ["year", "Yearly · 2 months free"]].map(([k, l]) => (
                  <button key={k} data-testid={`pro-interval-${k}`} onClick={() => setInterval_(k)}
                    className={`label-caps text-[10px] px-3 py-2 rounded-sm border transition-colors ${interval === k ? "border-[#C4B5FD] text-[#C4B5FD] bg-[#7C3AED]/15" : "border-white/12 text-zinc-400"}`}>{l}</button>
                ))}
              </div>
              <div className="mt-6 flex items-end gap-3">
                <div className="font-anton text-6xl leading-none" data-testid="pro-price">${shown}</div>
                <div className="text-zinc-500 text-sm mb-2">/{interval}</div>
                {founder && <div className="text-zinc-600 text-sm mb-2 line-through">${price.amount}</div>}
              </div>
              {founder && <div className="mt-3 label-caps text-[10px] text-[#CCFF00] flex items-center gap-1" data-testid="pro-founder-note"><Sparkles size={10} /> Founding artist · 50% off for life</div>}
              <button data-testid="pro-subscribe-btn" onClick={subscribe} disabled={busy || (user && user.role !== "artist")} className="btn-lime w-full mt-8 !py-3 disabled:opacity-40">
                {busy ? <Loader2 size={14} className="animate-spin inline" /> : user ? "Go Pro" : "Sign in to go Pro"}
              </button>
              <div className="text-[10px] text-zinc-600 mt-3">Cancel anytime. Card processed by Stripe.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
