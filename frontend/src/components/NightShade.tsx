import { useMemo } from "react";
import { Pane, Polygon, Polyline } from "react-leaflet";
import { TWILIGHT_LEVELS, nightPolygons } from "../utils/solar";

type Props = { timeMs: number; style: "dark" | "satellite" | "street" };

/** Night colour per map: a blue tint reads on the already-dark map, black darkens photos. */
const TONE = {
  dark: { fill: "#1d4ed8", opacity: [0.2, 0.16, 0.14, 0.12], line: "#93c5fd" },
  satellite: { fill: "#020617", opacity: [0.28, 0.18, 0.14, 0.12], line: "#f5d78a" },
  street: { fill: "#0b1b4d", opacity: [0.3, 0.16, 0.12, 0.1], line: "#475569" },
} as const;

/** Shades the night side of the Earth, with the three twilight steps, for the given moment. */
export default function NightShade({ timeMs, style }: Props) {
  const tone = TONE[style];
  // The terminator moves a quarter of a degree a minute: redrawing more often is wasted work.
  const minute = Math.floor(timeMs / 60_000);
  const bands = useMemo(
    () => TWILIGHT_LEVELS.map(level => nightPolygons(minute * 60_000, level)),
    [minute],
  );

  // The terminator itself: the real edge of the first band, without the closing edges along
  // the poles and the date line that the filled polygon needs.
  const edges = useMemo(
    () =>
      bands[0].map(poly => {
        const closedAtPole = Math.abs(poly[0][0]) === 90 && Math.abs(poly[poly.length - 1][0]) === 90;
        return closedAtPole ? poly.slice(1, -1) : poly;
      }),
    [bands],
  );

  return (
    <Pane name="night" style={{ zIndex: 250, pointerEvents: "none" }}>
      {bands.map((polys, i) => (
        <Polygon
          key={TWILIGHT_LEVELS[i]}
          positions={polys}
          pathOptions={{
            stroke: false,
            fillColor: tone.fill,
            fillOpacity: tone.opacity[i],
            interactive: false,
          }}
        />
      ))}
      {edges.map((line, i) => (
        <Polyline
          key={`edge-${i}`}
          positions={line}
          pathOptions={{ color: tone.line, weight: 1, opacity: 0.4, interactive: false }}
        />
      ))}
    </Pane>
  );
}
