import { useCallback, useSyncExternalStore } from "react";

const KEY = "satellite-tracker:favourites";
const EVENT = "satellite-tracker:favourites-changed";

function read(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

// useSyncExternalStore needs a stable snapshot until the data changes.
let cache: string[] = read();
let cacheRaw = JSON.stringify(cache);

function snapshot(): string[] {
  const next = read();
  const raw = JSON.stringify(next);
  if (raw !== cacheRaw) {
    cache = next;
    cacheRaw = raw;
  }
  return cache;
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange); // another tab changed it
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function write(list: string[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* storage unavailable (private window): the star just won't stick */
  }
  cache = list;
  cacheRaw = JSON.stringify(list);
  window.dispatchEvent(new Event(EVENT));
}

/** Starred satellites, remembered in this browser. */
export function useFavourites() {
  const favourites = useSyncExternalStore(subscribe, snapshot, () => []);

  const toggle = useCallback((name: string) => {
    const current = read();
    write(current.includes(name) ? current.filter(n => n !== name) : [...current, name]);
  }, []);

  return { favourites, isFavourite: (name: string) => favourites.includes(name), toggle };
}
