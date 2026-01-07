import { useState } from "react";

export function useObserver() {
  const [location, setLocation] = useState<{lat: number; lon: number} | null>(null);

  function requestLocation() {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude
        });
      },
      () => alert("Location permission denied")
    );
  }

  return { location, requestLocation };
}
