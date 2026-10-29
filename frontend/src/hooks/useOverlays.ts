import { useCallback, useState } from "react";

export type OverlayId = "track" | "night" | "footprint" | "labels" | "sky";

const KEY = "satellite-tracker:overlays";
const DEFAULTS: Record<OverlayId, boolean> = {
  track: true,
  night: true,
  footprint: true,
  labels: true,
  sky: true,
};

function load(): Record<OverlayId, boolean> {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? "{}");
    const out = { ...DEFAULTS };
    for (const id of Object.keys(DEFAULTS) as OverlayId[]) {
      if (typeof saved[id] === "boolean") out[id] = saved[id];
    }
    return out;
  } catch {
    return { ...DEFAULTS };
  }
}

/** Which map overlays are switched on; remembered between visits. */
export function useOverlays() {
  const [overlays, setOverlays] = useState(load);

  const toggle = useCallback((id: OverlayId) => {
    setOverlays(prev => {
      const next = { ...prev, [id]: !prev[id] };
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        /* private mode: the choice just lasts until the page closes */
      }
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setOverlays({ ...DEFAULTS });
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }, []);

  return { overlays, toggle, reset };
}
