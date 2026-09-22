import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const ORIGIN = typeof window !== "undefined" ? window.location.origin : "";

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("hom_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const fileUrl = (path) => (path ? `${API}/files/${path}` : null);
// Private assets (dispute photos, DM images) come back from the API as short-lived signed paths
export const privateFileUrl = (signedPath) => (!signedPath ? null : signedPath.startsWith("http") ? signedPath : `${BACKEND_URL}${signedPath}`);
// Resized JPEG variant for grids/feeds (240 | 480 | 960)
export const thumbUrl = (path, w = 480) => (path ? (path.startsWith("http") ? path : `${API}/files/${path}?w=${w}`) : null);

export function copyText(t) {
  const fallback = () => { const ta = document.createElement("textarea"); ta.value = t; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); } catch {} document.body.removeChild(ta); };
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(t).catch(fallback); else fallback();
}
