import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { api } from "../api";
import { useTranslation } from "react-i18next";

export function Login() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState(null);
  const { login, verifyTwoFactor } = useAuth();
  const nav = useNavigate();
  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState("");
  const [remember, setRemember] = useState(false);

  const submitCode = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await verifyTwoFactor(challenge.challenge_token, code, remember);
      toast.success(t("auth.welcome_back"));
      routeByRole(u);
    } catch (er) { toast.error(er?.response?.data?.detail || "Wrong code"); }
    finally { setBusy(false); }
  };
  const resendCode = async () => {
    try { await api.post("/auth/2fa/resend", { challenge_token: challenge.challenge_token }); toast.success("New code sent"); }
    catch (er) { toast.error(er?.response?.data?.detail || "Couldn't resend"); }
  };

  const routeByRole = (u) => {
    if (u.role === "admin") nav("/admin");
    else if (u.role === "artist") nav("/studio");
    else nav("/dashboard");
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(email, password);
      if (u.requires_2fa) { setChallenge(u); return; }
      toast.success(t("auth.welcome_back"));
      routeByRole(u);
    } catch { toast.error(t("auth.invalid")); }
    finally { setBusy(false); }
  };

  const demoLogin = async (key) => {
    const creds = key === "artist"
      ? { email: "demo.artist@artcorestudio.net", password: "DemoArtist2026!" }
      : { email: "demo.collector@artcorestudio.net", password: "DemoCollector2026!" };
    setDemoBusy(key);
    try {
      const u = await login(creds.email, creds.password);
      toast.success(`Signed in as demo ${key}`);
      routeByRole(u);
    } catch { toast.error("Demo login failed — try again in a sec"); }
    finally { setDemoBusy(null); }
  };

  if (challenge) {
    return (
      <div data-testid="twofa-challenge-page" className="max-w-md mx-auto px-6 pt-24 pb-32">
        <div className="label-caps text-[#CCFF00]">Two-factor login</div>
        <h1 className="font-anton text-5xl uppercase mt-4 mb-6 leading-none">One more<br />step.</h1>
        <p className="text-sm text-zinc-400 mb-8">
          {challenge.method === "email" ? "We emailed you a 6-digit code." : "Open your authenticator app and enter the 6-digit code."} You can also use a recovery code.
        </p>
        <form onSubmit={submitCode} className="space-y-5">
          <input data-testid="twofa-login-code" autoFocus required value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" placeholder="000000" maxLength={16}
            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00] font-mono tracking-widest text-center text-xl" />
          <label className="flex items-center gap-3 text-sm text-zinc-300 cursor-pointer select-none">
            <input data-testid="twofa-remember-device" type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="accent-[#CCFF00] w-4 h-4" />
            Trust this device for 30 days
          </label>
          <button data-testid="twofa-login-submit" disabled={busy} className="btn-lime w-full">{busy ? t("auth.signing_in") : "Verify"}</button>
        </form>
        <div className="mt-6 flex justify-between text-xs text-zinc-500">
          <button data-testid="twofa-back-btn" type="button" onClick={() => { setChallenge(null); setCode(""); }} className="hover:text-white">← Back</button>
          {challenge.method === "email" && <button data-testid="twofa-resend-btn" type="button" onClick={resendCode} className="text-[#CCFF00] hover:underline">Resend code</button>}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="login-page" className="max-w-md mx-auto px-6 pt-24 pb-32">
      <div className="label-caps text-[#CCFF00]">{t("auth.sign_in")}</div>
      <h1 className="font-anton text-6xl uppercase mt-4 mb-8 leading-none">{t("auth.welcome_1")}<br />{t("auth.welcome_2")}</h1>

      {/* One-click demo sign-in */}
      <div className="mb-8">
        <div className="label-caps text-zinc-500 mb-3">{t("auth.one_tap")}</div>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            data-testid="demo-artist-btn"
            onClick={() => demoLogin("artist")}
            disabled={!!demoBusy}
            className="border border-[#CCFF00]/40 bg-[#CCFF00]/10 text-[#CCFF00] hover:bg-[#CCFF00]/20 label-caps py-3 rounded-sm text-xs transition-colors">
            {demoBusy === "artist" ? t("auth.signing_in") : t("auth.enter_artist")}
          </button>
          <button
            type="button"
            data-testid="demo-collector-btn"
            onClick={() => demoLogin("collector")}
            disabled={!!demoBusy}
            className="border border-[#7C3AED]/40 bg-[#7C3AED]/10 text-[#7C3AED] hover:bg-[#7C3AED]/20 label-caps py-3 rounded-sm text-xs transition-colors">
            {demoBusy === "collector" ? t("auth.signing_in") : t("auth.enter_collector")}
          </button>
        </div>
        <div className="text-[10px] text-zinc-500 mt-2">
          {t("auth.demo_note")}
        </div>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <div className="flex-1 h-px bg-white/8" />
        <div className="text-[10px] text-zinc-500 label-caps">{t("auth.or_normal")}</div>
        <div className="flex-1 h-px bg-white/8" />
      </div>

      <form onSubmit={submit} className="space-y-5">
        <input data-testid="login-email" required type="email" placeholder={t("auth.email")} value={email} onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <input data-testid="login-password" required type="password" placeholder={t("auth.password")} value={password} onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <button data-testid="login-submit" disabled={busy} className="btn-lime w-full mt-4">{busy ? t("auth.signing_in") : t("auth.sign_in")}</button>
      </form>
      <div className="mt-8 text-sm text-zinc-400">
        {t("auth.no_account")} <Link to="/register" data-testid="link-register" className="text-[#CCFF00] hover:underline">{t("auth.join_art_core")}</Link>
      </div>
    </div>
  );
}

export function Register() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [role, setRole] = useState(params.get("role") === "artist" ? "artist" : "buyer");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const { register } = useAuth();
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await register({ email, password, name, role });
      toast.success(t("auth.welcome_to"));
      nav(u.role === "artist" ? "/onboarding" : "/dashboard");
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <div data-testid="register-page" className="max-w-md mx-auto px-6 pt-24 pb-32">
      <div className="label-caps text-[#CCFF00]">{t("auth.join")}</div>
      <h1 className="font-anton text-6xl uppercase mt-4 mb-12 leading-none">{t("auth.enter_1")}<br />{t("auth.enter_2")}</h1>
      <div className="grid grid-cols-2 gap-3 mb-6">
        <button type="button" data-testid="role-buyer" onClick={() => setRole("buyer")}
          className={`py-3 label-caps text-xs border rounded-sm ${role === "buyer" ? "bg-[#CCFF00] text-black border-[#CCFF00]" : "border-white/15 text-zinc-300 hover:border-[#CCFF00]"}`}>{t("auth.collector")}</button>
        <button type="button" data-testid="role-artist" onClick={() => setRole("artist")}
          className={`py-3 label-caps text-xs border rounded-sm ${role === "artist" ? "bg-[#CCFF00] text-black border-[#CCFF00]" : "border-white/15 text-zinc-300 hover:border-[#CCFF00]"}`}>{t("auth.artist")}</button>
      </div>
      <form onSubmit={submit} className="space-y-5">
        <input data-testid="register-name" required placeholder={t("auth.full_name")} value={name} onChange={(e) => setName(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <input data-testid="register-email" required type="email" placeholder={t("auth.email")} value={email} onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <input data-testid="register-password" required type="password" placeholder={t("auth.password_min")} value={password} onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <button data-testid="register-submit" disabled={busy} className="btn-lime w-full mt-4">{busy ? t("auth.creating") : t("auth.create_account")}</button>
      </form>
      <div className="mt-8 text-sm text-zinc-400">
        {t("auth.already")} <Link to="/login" data-testid="link-login" className="text-[#CCFF00] hover:underline">{t("auth.sign_in_link")}</Link>
      </div>
    </div>
  );
}
