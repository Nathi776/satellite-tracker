import { useCallback, useEffect, useState } from "react";
import { fetchPushKey, postJson } from "../api";

type Where = { lat: number; lon: number } | null;
export type PushStatus = "checking" | "unsupported" | "insecure" | "unavailable" | "blocked" | "off" | "on";

const KEY = "satellite-tracker:alerts";
const LEADS = [5, 10, 20, 30];
export const ALERT_LEADS = LEADS;

function loadPrefs(): { lead: number; visibleOnly: boolean } {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "{}");
    return { lead: LEADS.includes(v.lead) ? v.lead : 10, visibleOnly: v.visibleOnly !== false };
  } catch {
    return { lead: 10, visibleOnly: true };
  }
}

const b64ToBytes = (b64: string) => {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, c => c.charCodeAt(0));
};

const swUrl = () => `${import.meta.env.BASE_URL}sw.js`;

/** Pass alerts as push notifications: subscribe this browser, keep the server told where you are. */
export function usePushAlerts(where: Where) {
  const [status, setStatus] = useState<PushStatus>("checking");
  const [prefs, setPrefs] = useState(loadPrefs);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supported =
    typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

  const currentSubscription = useCallback(async () => {
    const reg = await navigator.serviceWorker.getRegistration(swUrl());
    return reg ? reg.pushManager.getSubscription() : null;
  }, []);

  // what is this browser's state right now?
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!supported) return setStatus("unsupported");
      if (!window.isSecureContext) return setStatus("insecure");
      try {
        const key = await fetchPushKey();
        if (!key.enabled) return !cancelled && setStatus("unavailable");
        if (Notification.permission === "denied") return !cancelled && setStatus("blocked");
        const sub = await currentSubscription();
        if (!cancelled) setStatus(sub ? "on" : "off");
      } catch {
        if (!cancelled) setStatus("unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [supported, currentSubscription]);

  const sync = useCallback(
    async (sub: PushSubscription, lead: number, visibleOnly: boolean, at: NonNullable<Where>) => {
      await postJson("/push/subscribe", {
        subscription: sub.toJSON(),
        lat: at.lat,
        lon: at.lon,
        lead_minutes: lead,
        visible_only: visibleOnly,
      });
    },
    [],
  );

  // keep the server's copy of the settings and location up to date while alerts are on
  const lat = where?.lat;
  const lon = where?.lon;
  useEffect(() => {
    if (status !== "on" || lat === undefined || lon === undefined) return;
    let cancelled = false;
    (async () => {
      try {
        const sub = await currentSubscription();
        if (sub && !cancelled) await sync(sub, prefs.lead, prefs.visibleOnly, { lat, lon });
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status, lat, lon, prefs, currentSubscription, sync]);

  const setPref = useCallback((next: Partial<{ lead: number; visibleOnly: boolean }>) => {
    setPrefs(prev => {
      const merged = { ...prev, ...next };
      try {
        localStorage.setItem(KEY, JSON.stringify(merged));
      } catch {
        /* not remembered: fine */
      }
      return merged;
    });
  }, []);

  const enable = useCallback(async () => {
    if (!where) return;
    setBusy(true);
    setError(null);
    try {
      const permission = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
      if (permission !== "granted") {
        setStatus("blocked");
        return;
      }
      const { public_key } = await fetchPushKey();
      if (!public_key) throw new Error("Alerts are not available on this server");
      await navigator.serviceWorker.register(swUrl());
      const reg = await navigator.serviceWorker.ready;
      const sub =
        (await reg.pushManager.getSubscription()) ??
        (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(public_key) }));
      await sync(sub, prefs.lead, prefs.visibleOnly, where);
      setStatus("on");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [where, prefs, sync]);

  const disable = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const sub = await currentSubscription();
      if (sub) {
        const endpoint = sub.endpoint;
        await sub.unsubscribe();
        await postJson("/push/unsubscribe", { endpoint }).catch(() => undefined);
      }
      setStatus("off");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [currentSubscription]);

  const sendTest = useCallback(async () => {
    setError(null);
    try {
      const sub = await currentSubscription();
      if (sub) await postJson("/push/test", { endpoint: sub.endpoint });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [currentSubscription]);

  return { status, prefs, setPref, enable, disable, sendTest, busy, error };
}
