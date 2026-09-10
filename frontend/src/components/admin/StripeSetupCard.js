import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { CreditCard, ExternalLink, Loader2, ShieldCheck, AlertTriangle, RefreshCw } from "lucide-react";
import { api } from "../../api";

const inputCls = "w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 text-sm outline-none focus:border-[#CCFF00] font-mono";

function Pill({ ok, label }) {
  return (
    <span className={`label-caps text-[10px] px-2 py-1 rounded-sm border ${ok ? "border-[#CCFF00]/40 text-[#CCFF00] bg-[#CCFF00]/5" : "border-[#F5A623]/40 text-[#F5A623] bg-[#F5A623]/5"}`}>
      {label}
    </span>
  );
}

export function StripeSetupCard() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [keys, setKeys] = useState({ live_secret_key: "", live_publishable_key: "", live_webhook_secret: "" });

  const load = () => api.get("/admin/stripe/status").then((r) => setStatus(r.data)).catch(() => toast.error("Couldn't load Stripe status"));
  useEffect(() => { load(); }, []);

  const saveKeys = async () => {
    const payload = Object.fromEntries(Object.entries(keys).filter(([, v]) => v.trim()));
    if (!Object.keys(payload).length) return toast.error("Paste at least one key");
    setBusy(true);
    try {
      await api.patch("/admin/stripe/config", payload);
      toast.success("Live keys saved");
      setKeys({ live_secret_key: "", live_publishable_key: "", live_webhook_secret: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Couldn't save keys"); }
    finally { setBusy(false); }
  };

  const switchMode = async (mode) => {
    if (mode === "live" && !window.confirm("Switch to LIVE mode? Real cards will be charged from now on.")) return;
    setBusy(true);
    try {
      await api.patch("/admin/stripe/config", { mode });
      toast.success(mode === "live" ? "Art Core is LIVE" : "Back in test mode");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Couldn't switch mode"); }
    finally { setBusy(false); }
  };

  if (!status) return <div className="label-caps text-zinc-500 py-8">Loading Stripe status...</div>;
  const live = status.mode === "live";
  const acct = status.account;

  return (
    <div className="space-y-6 max-w-3xl" data-testid="stripe-setup-card">
      <div className={`glass-card p-8 rounded-sm border ${live ? "border-[#CCFF00]/40" : "border-[#F5A623]/30"}`}>
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="label-caps text-[#CCFF00] flex items-center gap-2"><CreditCard size={12} /> Stripe · Platform Account</div>
            <div className="font-anton text-3xl uppercase mt-3" data-testid="stripe-mode-label">
              {live ? <span className="text-[#CCFF00]">Live mode</span> : <span className="text-[#F5A623]">Test mode</span>}
            </div>
            <div className="text-xs text-zinc-500 mt-2 max-w-lg">
              {live ? "Real payments are flowing. Your platform fee lands in this account's balance." :
                "Cards are not charged for real. Claim the sandbox below to make it your Stripe account, then paste live keys and flip the switch."}
            </div>
          </div>
          <button data-testid="stripe-refresh-btn" onClick={load} className="btn-ghost !py-2 !px-3 text-xs flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
        </div>

        <div className="grid sm:grid-cols-2 gap-4 mt-8">
          <div className="border border-white/8 rounded-sm p-4 bg-white/[0.02]">
            <div className="label-caps text-zinc-500 text-[10px]">Account</div>
            {acct ? (
              <>
                <div className="font-unbounded text-sm mt-2 truncate" data-testid="stripe-account-name">{acct.business_name || acct.email || acct.id}</div>
                <div className="text-[11px] text-zinc-500 font-mono mt-1">{acct.id} · {acct.country || "—"} · {(acct.default_currency || "usd").toUpperCase()}</div>
                <div className="flex flex-wrap gap-2 mt-3">
                  <Pill ok={acct.charges_enabled} label={acct.charges_enabled ? "Charges on" : "Charges off"} />
                  <Pill ok={acct.payouts_enabled} label={acct.payouts_enabled ? "Payouts on" : "Payouts off"} />
                  <Pill ok={acct.details_submitted} label={acct.details_submitted ? "Details complete" : "Details pending"} />
                </div>
              </>
            ) : (
              <div className="text-xs text-[#F5A623] mt-2 flex items-center gap-1"><AlertTriangle size={12} /> {status.error || "Unavailable"}</div>
            )}
          </div>
          <div className="border border-white/8 rounded-sm p-4 bg-white/[0.02]">
            <div className="label-caps text-zinc-500 text-[10px]">Wiring</div>
            <div className="flex flex-wrap gap-2 mt-3">
              <Pill ok={status.webhook_configured} label={status.webhook_configured ? "Webhook secret set" : "No webhook secret"} />
              <Pill ok={status.live_keys_saved} label={status.live_keys_saved ? `Live keys ${status.live_secret_masked}` : "No live keys yet"} />
            </div>
            <div className="text-xs text-zinc-400 mt-3" data-testid="stripe-connected-artists">{status.connected_artists} artist{status.connected_artists === 1 ? "" : "s"} connected for auto-payouts</div>
          </div>
        </div>

        {status.onboarding_url && !live && (
          <a data-testid="stripe-claim-link" href={status.onboarding_url} target="_blank" rel="noreferrer"
            className="btn-lime mt-6 inline-flex items-center gap-2">
            Claim this Stripe account <ExternalLink size={14} />
          </a>
        )}
      </div>

      <div className="glass-card p-8 rounded-sm">
        <div className="label-caps text-zinc-400 flex items-center gap-2"><ShieldCheck size={12} /> Go live</div>
        <ol className="text-xs text-zinc-500 mt-3 space-y-1 list-decimal list-inside">
          <li>Claim the account above and finish Stripe's business + bank verification.</li>
          <li>In Stripe → Developers → API keys, copy your <span className="text-zinc-300">live</span> secret and publishable keys.</li>
          <li>In Stripe → Developers → Webhooks, add <span className="font-mono text-zinc-300">{window.location.origin}/api/stripe/webhook</span> for <span className="font-mono">checkout.session.completed</span> and <span className="font-mono">account.updated</span>; paste its signing secret.</li>
          <li>Enable Connect → Express in Stripe so artists can onboard.</li>
        </ol>
        <div className="grid gap-3 mt-6">
          <input data-testid="stripe-live-secret-input" type="password" autoComplete="off" placeholder="sk_live_..." value={keys.live_secret_key}
            onChange={(e) => setKeys({ ...keys, live_secret_key: e.target.value })} className={inputCls} />
          <input data-testid="stripe-live-publishable-input" placeholder="pk_live_..." value={keys.live_publishable_key}
            onChange={(e) => setKeys({ ...keys, live_publishable_key: e.target.value })} className={inputCls} />
          <input data-testid="stripe-live-webhook-input" type="password" autoComplete="off" placeholder="whsec_... (live webhook signing secret)" value={keys.live_webhook_secret}
            onChange={(e) => setKeys({ ...keys, live_webhook_secret: e.target.value })} className={inputCls} />
        </div>
        <div className="flex flex-wrap gap-3 mt-5">
          <button data-testid="stripe-save-keys-btn" onClick={saveKeys} disabled={busy} className="btn-ghost">
            {busy ? <Loader2 size={14} className="animate-spin inline" /> : "Save live keys"}
          </button>
          {live ? (
            <button data-testid="stripe-switch-test-btn" onClick={() => switchMode("test")} disabled={busy} className="btn-ghost">Switch to test mode</button>
          ) : (
            <button data-testid="stripe-switch-live-btn" onClick={() => switchMode("live")} disabled={busy || !status.live_keys_saved} className="btn-lime disabled:opacity-40">Switch to live</button>
          )}
        </div>
      </div>
    </div>
  );
}
