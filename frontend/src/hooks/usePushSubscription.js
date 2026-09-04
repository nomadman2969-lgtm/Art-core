import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { toast } from "sonner";

// url-safe base64 -> Uint8Array
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; ++i) out[i] = raw.charCodeAt(i);
  return out;
}

/**
 * Manage the browser PushSubscription for the logged-in user.
 * Returns { supported, permission, subscribed, loading, enable, disable }.
 */
export default function usePushSubscription() {
  const supported =
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window;

  const [permission, setPermission] = useState(supported ? Notification.permission : "denied");
  const [subscribed, setSubscribed] = useState(false);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!supported) return;
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      setSubscribed(!!sub);
      setPermission(Notification.permission);
    } catch {
      /* ignore */
    }
  }, [supported]);

  useEffect(() => { refresh(); }, [refresh]);

  const enable = useCallback(async () => {
    if (!supported) { toast.error("Push not supported in this browser"); return false; }
    setLoading(true);
    try {
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== "granted") {
        toast.error("Notifications blocked — enable in site settings");
        return false;
      }
      const reg = await navigator.serviceWorker.ready;
      const { data } = await api.get("/push/vapid-public-key");
      const applicationServerKey = urlBase64ToUint8Array(data.public_key);
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey });
      const raw = sub.toJSON();
      await api.post("/push/subscribe", {
        endpoint: raw.endpoint,
        keys: { p256dh: raw.keys.p256dh, auth: raw.keys.auth },
      });
      setSubscribed(true);
      toast.success("Push notifications on");
      return true;
    } catch (e) {
      toast.error(e?.message || "Failed to enable push");
      return false;
    } finally {
      setLoading(false);
    }
  }, [supported]);

  const disable = useCallback(async () => {
    if (!supported) return;
    setLoading(true);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        const raw = sub.toJSON();
        await api.post("/push/unsubscribe", { endpoint: raw.endpoint }).catch(() => null);
        await sub.unsubscribe();
      }
      setSubscribed(false);
      toast.success("Push notifications off");
    } catch (e) {
      toast.error(e?.message || "Failed to disable");
    } finally {
      setLoading(false);
    }
  }, [supported]);

  const test = useCallback(async () => {
    try { await api.post("/push/test", {}); toast("Sent test push"); }
    catch { toast.error("Test push failed"); }
  }, []);

  return { supported, permission, subscribed, loading, enable, disable, test, refresh };
}
