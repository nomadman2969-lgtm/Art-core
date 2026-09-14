import React, { createContext, useContext, useEffect, useState } from "react";
import i18n, { normalizeLang } from "../i18n";
import { api } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  useEffect(() => { if (user?.language && normalizeLang(user.language) !== i18n.language) i18n.changeLanguage(normalizeLang(user.language)); }, [user?.language]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("hom_token");
    if (!token) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => { localStorage.removeItem("hom_token"); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password, device_token: localStorage.getItem("hom_device") || null });
    if (r.data.requires_2fa) return { requires_2fa: true, method: r.data.method, challenge_token: r.data.challenge_token };
    localStorage.setItem("hom_token", r.data.token);
    setUser(r.data.user);
    return r.data.user;
  };
  const demoSignIn = async (role) => {
    const r = await api.post("/auth/demo-login", { role });
    localStorage.setItem("hom_token", r.data.token);
    setUser(r.data.user);
    return r.data.user;
  };
  const verifyTwoFactor = async (challenge_token, code, rememberDevice = false) => {
    const device_label = `${navigator.platform || "Device"} · ${/Mobile|Android|iPhone/i.test(navigator.userAgent) ? "Mobile" : "Desktop"} browser`;
    const r = await api.post("/auth/2fa/verify-login", { challenge_token, code, remember_device: rememberDevice, device_label });
    if (r.data.device_token) localStorage.setItem("hom_device", r.data.device_token);
    localStorage.setItem("hom_token", r.data.token);
    setUser(r.data.user);
    return r.data.user;
  };
  const register = async (payload) => {
    const r = await api.post("/auth/register", payload);
    localStorage.setItem("hom_token", r.data.token);
    setUser(r.data.user);
    return r.data.user;
  };
  const logout = () => { localStorage.removeItem("hom_token"); setUser(null); };
  const refresh = async () => {
    const r = await api.get("/auth/me");
    setUser(r.data);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh, setUser, verifyTwoFactor, demoSignIn }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
