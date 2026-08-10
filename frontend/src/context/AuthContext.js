import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
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
    const r = await api.post("/auth/login", { email, password });
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
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
