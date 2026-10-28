import { useState } from "react";

type Location = { lat: number; lon: number };
const KEY = "satellite-tracker:location";

// Remembered for this browser tab only, so the satellite page and the map agree.
function load(): Location | null {
  try {
    const v = JSON.parse(sessionStorage.getItem(KEY) ?? "null");
    return v && typeof v.lat === "number" && typeof v.lon === "number" ? { lat: v.lat, lon: v.lon } : null;
  } catch {
    return null;
  }
}

function save(loc: Location) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(loc));
  } catch {
    /* storage unavailable: fine, it just isn't remembered */
  }
}

export function useObserver() {
  const [location, setLocation] = useState<Location | null>(load);

  function requestLocation() {
    if (!("geolocation" in navigator)) {
      alert("Geolocation is not supported by this browser");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const loc = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        save(loc);
        setLocation(loc);
      },
      (err) => alert(`Could not get your location: ${err.message}`),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 },
    );
  }

  return { location, requestLocation };
}
