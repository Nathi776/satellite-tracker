import { useEffect, useState } from "react";

export type Route = { page: "map" } | { page: "satellite"; name: string };

export const satelliteHref = (name: string) => `#/satellite/${encodeURIComponent(name)}`;

export function parseHash(hash: string): Route {
  const m = /^#\/satellite\/(.+)$/.exec(hash);
  if (m) {
    try {
      return { page: "satellite", name: decodeURIComponent(m[1]) };
    } catch {
      /* malformed escape: fall through to the map */
    }
  }
  return { page: "map" };
}

/** Which page the URL hash points to: "#/satellite/ISS%20(ZARYA)" or the map. */
export function useHashRoute(): Route {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return parseHash(hash);
}
