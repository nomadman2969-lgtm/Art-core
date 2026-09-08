import { useEffect, useRef, useState } from "react";

const WS_BASE = (process.env.REACT_APP_BACKEND_URL || "").replace(/^http/, "ws");

// Subscribe to realtime rooms (user room is implicit via token). Reconnects with backoff.
export function useLive(rooms, onEvent) {
  const [connected, setConnected] = useState(false);
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;
  const key = (rooms || []).join(",");

  useEffect(() => {
    if (!WS_BASE) return undefined;
    let ws, timer, dead = false, attempt = 0;
    const open = () => {
      const token = localStorage.getItem("hom_token") || "";
      try { ws = new WebSocket(`${WS_BASE}/api/ws?token=${encodeURIComponent(token)}&rooms=${encodeURIComponent(key)}`); } catch { return; }
      ws.onopen = () => { attempt = 0; setConnected(true); };
      ws.onmessage = (e) => { try { cbRef.current?.(JSON.parse(e.data)); } catch {} };
      ws.onclose = () => {
        setConnected(false);
        if (dead) return;
        attempt += 1;
        timer = setTimeout(open, Math.min(15000, 1000 * 2 ** attempt));
      };
      ws.onerror = () => { try { ws.close(); } catch {} };
    };
    open();
    const ping = setInterval(() => { if (ws?.readyState === 1) ws.send('{"type":"ping"}'); }, 25000);
    return () => { dead = true; clearInterval(ping); clearTimeout(timer); try { ws?.close(); } catch {} };
  }, [key]);

  return connected;
}
