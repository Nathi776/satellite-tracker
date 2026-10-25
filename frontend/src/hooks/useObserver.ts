import { useState } from "react";

export function useObserver() {
  const [location, setLocation] = useState<{ lat: number; lon: number } | null>(null);

  function requestLocation() {
    if (!("geolocation" in navigator)) {
      alert("Geolocation is not supported by this browser");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
        });
      },
      (err) => alert(`Could not get your location: ${err.message}`),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 },
    );
  }

  return { location, requestLocation };
}
