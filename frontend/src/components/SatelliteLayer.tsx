import { useEffect, useMemo, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { SatellitePos } from "../api";
import { groupColor } from "../utils/groups";

type Props = {
  sats: SatellitePos[];
  selectedName: string | null;
  onSelect: (name: string) => void;
};

// Above this many satellites the dots shrink so a dense group (Starlink) stays readable.
const DENSE_AT = 400;

/**
 * Draws every satellite as a dot on ONE canvas.
 *
 * Rendering thousands of <Marker>/<CircleMarker> React elements and re-rendering them every
 * second is slow. Here the Leaflet markers are created once per satellite and only moved
 * on each tick; Leaflet's canvas renderer repaints them in a single frame.
 */
export default function SatelliteLayer({ sats, selectedName, onSelect }: Props) {
  const map = useMap();
  const renderer = useMemo(() => L.canvas({ padding: 0.5 }), []);
  const group = useRef<L.LayerGroup | null>(null);
  const markers = useRef(new Map<string, L.CircleMarker>());
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;

  useEffect(() => {
    const layer = L.layerGroup().addTo(map);
    const current = markers.current;
    group.current = layer;
    return () => {
      layer.remove();
      current.clear();
      group.current = null;
    };
  }, [map]);

  useEffect(() => {
    const layer = group.current;
    if (!layer) return;
    const current = markers.current;
    const dense = sats.length > DENSE_AT;
    const seen = new Set<string>();

    for (const sat of sats) {
      seen.add(sat.name);
      const selected = sat.name === selectedName;
      const style: L.CircleMarkerOptions = {
        radius: selected ? 8 : dense ? 2.5 : 4.5,
        color: selected ? "#111" : "#fff",
        weight: selected ? 2.5 : 1,
        fillColor: groupColor(sat.group),
        fillOpacity: 0.95,
        bubblingMouseEvents: false, // a click on a dot is not a click on the map
      };

      let marker = current.get(sat.name);
      if (!marker) {
        marker = L.circleMarker([sat.lat, sat.lon], { renderer, ...style });
        marker.on("click", () => selectRef.current(sat.name));
        marker.bindTooltip(sat.name, { sticky: true, direction: "top", offset: [0, -4] });
        marker.addTo(layer);
        current.set(sat.name, marker);
      } else {
        marker.setLatLng([sat.lat, sat.lon]);
        marker.setStyle(style);
      }
      if (selected) marker.bringToFront();
    }

    for (const [name, marker] of current) {
      if (!seen.has(name)) {
        marker.remove();
        current.delete(name);
      }
    }
  }, [sats, selectedName, renderer]);

  return null;
}
