import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, Smartphone, Mail, Loader2, KeyRound, Copy } from "lucide-react";
import { api, copyText } from "../api";
import { useAuth } from "../context/AuthContext";

const inputCls = "w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00] font-mono tracking-widest text-center text-lg";

function RecoveryCodes({ codes }) {
  return (
    <div className="border border-[#F5A623]/40 bg-[#F5A623]/5 rounded-sm p-5" data-testid="recovery-codes">
      <div className="label-caps text-[#F5A623] flex items-center gap-2"><KeyRound size={12} /> Recovery codes — save these now</div>
      <div className="text-xs text-zinc-400 mt-2">Each works once if you lose your phone or email access. We won't show them again.</div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4 font-mono text-sm">
        {codes.map((c) => <div key={c} className="bg-black/40 border border-white/10 rounded-sm px-2 py-1.5 text-center" data-testid="recovery-code">{c}</div>)}
      </div>
      <button data-testid="copy-recovery-btn" onClick={() => { copyText(codes.join("\n")); toast.success("Copied"); }} className="btn-ghost !py-2 !px-3 text-xs mt-4 flex items-center gap-1"><Copy size={12} /> Copy all</button>
    </div>
  );
}

export default function Security() {
  const { refresh } = useAuth();
  const [status, setStatus] = useState(null);
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [recovery, setRecovery] = useState(null);

  const load = () => api.get("/auth/2fa/status").then((r) => setStatus(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const start = async (method) => {
    setBusy(true);
    try { const r = await api.post("/auth/2fa/setup", { method }); setSetup(r.data); setCode(""); }
    catch (e) { toast.error(e?.response?.data?.detail || "Couldn't start setup"); }
    finally { setBusy(false); }
  };
  const confirm = async (e) => {
    e.preventDefault(); setBusy(true);
    try {
      const r = await api.post("/auth/2fa/enable", { code });
      setRecovery(r.data.recovery_codes); setSetup(null); setCode("");
      toast.success("Two-factor login is on"); load(); refresh?.();
    } catch (er) { toast.error(er?.response?.data?.detail || "Wrong code"); }
    finally { setBusy(false); }
  };
  const disable = async (e) => {
    e.preventDefault(); setBusy(true);
    try {
      await api.post("/auth/2fa/disable", { password, code });
      toast.success("Two-factor login is off"); setCode(""); setPassword(""); setRecovery(null); load(); refresh?.();
    } catch (er) { toast.error(er?.response?.data?.detail || "Couldn't disable"); }
    finally { setBusy(false); }
  };
  const regen = async () => {
    const c = window.prompt("Enter a current 2FA code to generate new recovery codes");
    if (!c) return;
    try { const r = await api.post("/auth/2fa/recovery-codes", { code: c }); setRecovery(r.data.recovery_codes); toast.success("New codes generated"); load(); }
    catch (er) { toast.error(er?.response?.data?.detail || "Couldn't regenerate"); }
  };

  if (!status) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;

  return (
    <div data-testid="security-page" className="max-w-2xl mx-auto px-6 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00] flex items-center gap-2"><ShieldCheck size={12} /> Account security</div>
      <h1 className="font-anton text-4xl sm:text-5xl lg:text-6xl uppercase mt-3 leading-[0.9]">Two-factor<br />login</h1>
      <p className="text-zinc-400 text-sm mt-4 max-w-lg">A second step at sign-in keeps your studio, payouts and Stripe account safe even if your password leaks.</p>

      <div className={`mt-10 glass-card rounded-sm p-6 border ${status.enabled ? "border-[#CCFF00]/40" : "border-white/10"}`} data-testid="twofa-status-card">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="font-unbounded text-sm" data-testid="twofa-status-label">{status.enabled ? <span className="text-[#CCFF00]">✓ Enabled</span> : <span className="text-zinc-300">Not enabled</span>}</div>
            {status.enabled && <div className="text-xs text-zinc-500 mt-1">Method: {status.method === "totp" ? "Authenticator app" : "Email code"} · {status.recovery_codes_left} recovery codes left</div>}
          </div>
          {status.enabled && <button data-testid="regen-recovery-btn" onClick={regen} className="btn-ghost !py-2 !px-3 text-xs">New recovery codes</button>}
        </div>
      </div>

      {recovery && <div className="mt-6"><RecoveryCodes codes={recovery} /></div>}

      {!status.enabled && !setup && (
        <div className="grid sm:grid-cols-2 gap-4 mt-8">
          <button data-testid="setup-totp-btn" onClick={() => start("totp")} disabled={busy} className="glass-card rounded-sm p-6 text-left hover:border-[#CCFF00]/50 border border-white/10 transition-colors">
            <Smartphone size={20} className="text-[#CCFF00]" />
            <div className="font-unbounded text-sm mt-4">Authenticator app</div>
            <div className="text-xs text-zinc-500 mt-2">Google Authenticator, 1Password, Authy. Works offline. Recommended.</div>
          </button>
          <button data-testid="setup-email-btn" onClick={() => start("email")} disabled={busy} className="glass-card rounded-sm p-6 text-left hover:border-[#CCFF00]/50 border border-white/10 transition-colors">
            <Mail size={20} className="text-[#7C3AED]" />
            <div className="font-unbounded text-sm mt-4">Email code</div>
            <div className="text-xs text-zinc-500 mt-2">We email a 6-digit code each time you sign in.</div>
          </button>
        </div>
      )}

      {setup && (
        <form onSubmit={confirm} className="mt-8 glass-card rounded-sm p-6 space-y-5" data-testid="twofa-setup-form">
          {setup.method === "totp" ? (
            <>
              <div className="label-caps text-zinc-400">1 · Scan with your authenticator app</div>
              <div className="flex flex-col sm:flex-row gap-5 items-start">
                {setup.qr_image && <img src={setup.qr_image} alt="2FA QR" className="w-44 h-44 bg-white p-2 rounded-sm" data-testid="totp-qr" />}
                <div className="text-xs text-zinc-500 min-w-0">
                  Can't scan? Enter this key manually:
                  <div className="font-mono text-sm text-zinc-200 mt-2 break-all select-all" data-testid="totp-secret">{setup.secret}</div>
                </div>
              </div>
              <div className="label-caps text-zinc-400">2 · Enter the 6-digit code it shows</div>
            </>
          ) : (
            <div className="label-caps text-zinc-400">Enter the 6-digit code we emailed to {setup.sent_to}</div>
          )}
          <input data-testid="twofa-code-input" value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" placeholder="000000" maxLength={16} required className={inputCls} />
          <div className="flex gap-3">
            <button data-testid="twofa-confirm-btn" disabled={busy} className="btn-lime flex-1">{busy ? <Loader2 size={14} className="animate-spin inline" /> : "Turn on 2FA"}</button>
            <button type="button" data-testid="twofa-cancel-btn" onClick={() => setSetup(null)} className="btn-ghost">Cancel</button>
          </div>
        </form>
      )}

      {status.enabled && (
        <form onSubmit={disable} className="mt-8 border border-white/10 rounded-sm p-6 space-y-4" data-testid="twofa-disable-form">
          <div className="label-caps text-zinc-400">Turn off two-factor login</div>
          <input data-testid="disable-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Your password" required className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#FF4D4D]" />
          <input data-testid="disable-code-input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Current 2FA or recovery code" required className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#FF4D4D] font-mono" />
          <button data-testid="twofa-disable-btn" disabled={busy} className="btn-ghost !text-[#FF4D4D] !border-[#FF4D4D]/40">{busy ? <Loader2 size={14} className="animate-spin inline" /> : "Disable 2FA"}</button>
        </form>
      )}
    </div>
  );
}
