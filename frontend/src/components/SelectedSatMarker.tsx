import { useMemo } from "react";
import { Marker } from "react-leaflet";
import L from "leaflet";
import { groupColor } from "../utils/groups";

const glyph = `
<svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
  <g fill="none" stroke="#fff" stroke-width="1.6" stroke-linejoin="round">
    <rect x="12" y="12" width="8" height="8" rx="1.5" fill="currentColor"/>
    <rect x="1.5" y="13" width="8" height="6" rx="1" fill="#1e3a5f"/>
    <rect x="22.5" y="13" width="8" height="6" rx="1" fill="#1e3a5f"/>
    <path d="M9.5 16h2.5M20 16h2.5M16 12V8"/>
    <circle cx="16" cy="6.5" r="1.6" fill="#fff"/>
  </g>
</svg>`;

type Props = { name: string; lat: number; lon: number; group?: string };

/** A satellite-shaped marker with a pulsing ring, for the satellite the user picked. */
export default function SelectedSatMarker({ name, lat, lon, group }: Props) {
  const color = groupColor(group);
  const safe = name.replace(/[&<>"]/g, c => `&#${c.charCodeAt(0)};`);
  const icon = useMemo(
    () =>
      L.divIcon({
        className: "selsat",
        html: `<span class="selsat__ring" style="--c:${color}"></span><span class="selsat__glyph" style="color:${color}">${glyph}</span><span class="selsat__label">${safe}</span>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
      }),
    [color, safe],
  );
  return <Marker position={[lat, lon]} icon={icon} interactive={false} keyboard={false} zIndexOffset={1200} />;
}
