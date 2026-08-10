import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const { login } = useAuth();
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(email, password);
      toast.success("Welcome back");
      if (u.role === "admin") nav("/admin");
      else if (u.role === "artist") nav("/studio");
      else nav("/dashboard");
    } catch { toast.error("Invalid credentials"); }
    finally { setBusy(false); }
  };
  return (
    <div data-testid="login-page" className="max-w-md mx-auto px-6 pt-24 pb-32">
      <div className="label-caps text-[#CCFF00]">Sign In</div>
      <h1 className="font-anton text-6xl uppercase mt-4 mb-12 leading-none">Welcome<br />back.</h1>
      <form onSubmit={submit} className="space-y-5">
        <input data-testid="login-email" required type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <input data-testid="login-password" required type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <button data-testid="login-submit" disabled={busy} className="btn-lime w-full mt-4">{busy ? "Signing in..." : "Sign In"}</button>
      </form>
      <div className="mt-8 text-sm text-zinc-400">
        No account? <Link to="/register" data-testid="link-register" className="text-[#CCFF00] hover:underline">Join Art Core</Link>
      </div>
    </div>
  );
}

export function Register() {
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
      toast.success("Welcome to Art Core");
      nav(u.role === "artist" ? "/studio" : "/dashboard");
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <div data-testid="register-page" className="max-w-md mx-auto px-6 pt-24 pb-32">
      <div className="label-caps text-[#CCFF00]">Join</div>
      <h1 className="font-anton text-6xl uppercase mt-4 mb-12 leading-none">Enter<br />Art Core.</h1>
      <div className="grid grid-cols-2 gap-3 mb-6">
        <button type="button" data-testid="role-buyer" onClick={() => setRole("buyer")}
          className={`py-3 label-caps text-xs border rounded-sm ${role === "buyer" ? "bg-[#CCFF00] text-black border-[#CCFF00]" : "border-white/15 text-zinc-300 hover:border-[#CCFF00]"}`}>Collector</button>
        <button type="button" data-testid="role-artist" onClick={() => setRole("artist")}
          className={`py-3 label-caps text-xs border rounded-sm ${role === "artist" ? "bg-[#CCFF00] text-black border-[#CCFF00]" : "border-white/15 text-zinc-300 hover:border-[#CCFF00]"}`}>Artist</button>
      </div>
      <form onSubmit={submit} className="space-y-5">
        <input data-testid="register-name" required placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <input data-testid="register-email" required type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <input data-testid="register-password" required type="password" placeholder="Password (min 6)" value={password} onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-4 py-3 outline-none focus:border-[#CCFF00]" />
        <button data-testid="register-submit" disabled={busy} className="btn-lime w-full mt-4">{busy ? "Creating..." : "Create Account"}</button>
      </form>
      <div className="mt-8 text-sm text-zinc-400">
        Already inside? <Link to="/login" data-testid="link-login" className="text-[#CCFF00] hover:underline">Sign in</Link>
      </div>
    </div>
  );
}
