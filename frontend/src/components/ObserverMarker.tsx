import { useMemo } from "react";
import { Marker, Polygon } from "react-leaflet";
import L from "leaflet";
import { footprintPolygons } from "../utils/geo";

/**
 * Ground distance within which a satellite at ~500 km altitude rises above 10 degrees:
 * the practical "who can I see" radius for low-orbit satellites.
 */
const LEO_RANGE_KM = 1570;

const icon = L.divIcon({
  className: "you",
  html: '<span class="you__pulse"></span><span class="you__dot"></span><span class="you__label">You are here</span>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

export default function ObserverMarker({ lat, lon }: { lat: number; lon: number }) {
  const range = useMemo(() => footprintPolygons(lat, lon, LEO_RANGE_KM, 72), [lat, lon]);
  return (
    <>
      <Polygon
        positions={range}
        pathOptions={{
          color: "#3b82f6",
          weight: 1.2,
          dashArray: "4 6",
          fillColor: "#3b82f6",
          fillOpacity: 0.07,
          interactive: false,
        }}
      />
      <Marker position={[lat, lon]} icon={icon} keyboard={false} zIndexOffset={900} />
    </>
  );
}
