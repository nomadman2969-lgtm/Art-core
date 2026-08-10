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
