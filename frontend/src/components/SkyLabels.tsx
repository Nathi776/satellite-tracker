import L from "leaflet";
import { Marker } from "react-leaflet";
import type { VisibleSat } from "../api";
import { STATUS_STYLE } from "../utils/sky";

const esc = (s: string) => s.replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);

/** Name labels on the map for the satellites above your horizon (the rest stay plain dots). */
export default function SkyLabels({
  sats,
  skip,
  max = 6,
  onSelect,
}: {
  sats: VisibleSat[];
  /** name of the satellite that already has its own marker */
  skip: string | null;
  max?: number;
  onSelect: (name: string) => void;
}) {
  const shown = [...sats]
    .filter(s => s.name !== skip)
    .sort((a, b) => Number(b.naked_eye) - Number(a.naked_eye) || b.altitude_deg - a.altitude_deg)
    .slice(0, max);

  return (
    <>
      {shown.map(s => (
        <Marker
          key={s.name}
          position={[s.lat, s.lon]}
          zIndexOffset={400}
          icon={L.divIcon({
            className: "",
            html: `<div class="skylabel" style="--c:${STATUS_STYLE[s.status].color}"><i></i><span>${esc(s.name)}</span></div>`,
            iconSize: [0, 0],
          })}
          eventHandlers={{ click: () => onSelect(s.name) }}
        />
      ))}
    </>
  );
}
