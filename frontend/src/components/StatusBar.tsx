import { useSyncExternalStore } from "react";
import { cursorStore } from "../utils/cursorStore";
import "./status-bar.css";

type Props = {
  nowMs: number;
  travelAtMs: number | null;
  tracked: number | null;
  shown: number;
  /** satellites above the observer's horizon; null without a location */
  above: number | null;
  /** the satellite picked on the map, for its telemetry */
  selected: { name: string; alt_km?: number; speed_kms?: number; lat: number; lon: number } | null;
  /** seconds since the sky data was computed; null before the first answer */
  dataAgeS: number | null;
  stale: boolean;
  error: string | null;
};

const utc = (ms: number) =>
  new Date(ms).toLocaleString("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

const coord = (v: number, pos: string, neg: string, digits = 2) =>
  `${Math.abs(v).toFixed(digits)}°${v >= 0 ? pos : neg}`;

function age(s: number) {
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}

/** Thin bar under the map: time, pointer, counts, selected satellite telemetry, data health. */
export default function StatusBar({
  nowMs,
  travelAtMs,
  tracked,
  shown,
  above,
  selected,
  dataAgeS,
  stale,
  error,
}: Props) {
  const cursor = useSyncExternalStore(cursorStore.subscribe, cursorStore.get);
  const [date, time] = utc(travelAtMs ?? nowMs).split(", ");
  const ok = !stale && !error;

  return (
    <footer className="statusbar" aria-label="Status">
      <span className={`statusbar__time${travelAtMs !== null ? " is-travel" : ""}`}>
        {travelAtMs !== null && <span className="statusbar__tag">Time travel</span>}
        <strong>{time}</strong> UTC
      </span>
      <span>{date}</span>
      <span className="statusbar__sep" />
      <span className="statusbar__cursor" title="Pointer position">
        {cursor ? `${coord(cursor.lat, "N", "S")} ${coord(cursor.lon, "E", "W")}` : "Pointer —"}
      </span>
      <span className="statusbar__sep" />
      {tracked !== null && (
        <span>
          <b>{tracked.toLocaleString()}</b> tracked
        </span>
      )}
      <span>
        <b>{shown.toLocaleString()}</b> on map
      </span>
      {above !== null && (
        <span>
          <b>{above}</b> above you
        </span>
      )}
      {selected && (
        <>
          <span className="statusbar__sep" />
          <span className="statusbar__sel">
            <b>{selected.name}</b>
            {selected.alt_km !== undefined && <> · {Math.round(selected.alt_km).toLocaleString()} km</>}
            {selected.speed_kms !== undefined && <> · {selected.speed_kms.toFixed(2)} km/s</>}
            {" · "}
            {coord(selected.lat, "N", "S")} {coord(selected.lon, "E", "W")}
          </span>
        </>
      )}
      <span className="statusbar__grow" />
      <span className="statusbar__health" role="status">
        <span className="statusbar__led" style={{ background: ok ? "#4ade80" : "#ef4444" }} />
        {error
          ? "API error"
          : dataAgeS === null
            ? "Waiting for data"
            : stale
              ? `Sky data ${age(dataAgeS)} old`
              : `Live · sky data ${age(dataAgeS)} old`}
      </span>
    </footer>
  );
}
