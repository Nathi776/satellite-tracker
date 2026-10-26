import { useCallback } from "react";
import { fetchAfricaPasses } from "../api";
import { usePolling } from "../hooks/usePolling";
import { STATUS_STYLE, formatClock, formatDay, relativeTime } from "../utils/sky";

const REFRESH_MS = 5 * 60 * 1000;
const SHOWN = 12;

type Props = { lat: number; lon: number; nowMs: number };

/** Passes of African satellites over the observer in the next 24 h, visible or not. */
export default function AfricaPasses({ lat, lon, nowMs }: Props) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchAfricaPasses(lat, lon, 24, signal),
    [lat, lon],
  );
  const { data, error } = usePolling(fetcher, REFRESH_MS);

  const upcoming = (data?.passes ?? []).filter(p => new Date(p.set_time_utc).getTime() > nowMs);

  return (
    <>
      <h4>🌍 African satellites over you · 24 h</h4>
      {error && !data && <div className="sky-muted">Couldn’t load African passes.</div>}
      {data && upcoming.length === 0 && (
        <div className="sky-muted">No African satellite rises above 10° here in the next 24 hours.</div>
      )}
      {upcoming.slice(0, SHOWN).map(p => (
        <div className="sky-pass" key={`${p.name}-${p.rise_time_utc}`}>
          <div className="sky-pass__top">
            <strong>{p.name}</strong>
            <small>{p.country ?? ""}</small>
          </div>
          <div>
            {formatDay(p.rise_time_utc)} · {formatClock(p.rise_time_utc)}{" "}
            <small>({relativeTime(p.rise_time_utc, nowMs)})</small>
          </div>
          <small>
            {p.rise_direction} → {p.set_direction} · peaks at {Math.round(p.max_elevation_deg)}° ·{" "}
            {p.visibility === "visible" ? "visible to the eye" : STATUS_STYLE[p.visibility].hint}
          </small>
        </div>
      ))}
      {upcoming.length > SHOWN && <div className="sky-muted">+ {upcoming.length - SHOWN} more</div>}
    </>
  );
}
