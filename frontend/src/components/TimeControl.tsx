import { useState } from "react";
import "./map-ui.css";

type Props = {
  /** minutes from now: 0 = live, negative = past, positive = future */
  offsetMin: number;
  onChange: (offsetMin: number) => void;
  /** the moment being shown (ms since epoch) once the data for it has loaded, else null */
  shownAtMs: number | null;
  maxHours?: number;
};

export function formatOffset(min: number): string {
  if (min === 0) return "Live";
  const sign = min > 0 ? "+" : "−";
  const abs = Math.abs(min);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  return `${sign}${h ? `${h} h ` : ""}${m ? `${m} min` : ""}`.trim();
}

/** Scrub the map backwards and forwards in time. Position data is only as good as the TLE age. */
export default function TimeControl({ offsetMin, onChange, shownAtMs, maxHours = 24 }: Props) {
  const max = maxHours * 60;
  const live = offsetMin === 0;
  // On phones the control is a one-line pill until tapped; on desktop it is always open (CSS).
  const [open, setOpen] = useState(false);

  return (
    <div
      className={`timebar${open ? " timebar--open" : ""}`}
      role="group"
      aria-label="Time travel"
    >
      <div className="timebar__top">
        <strong>
          {live ? (
            <>
              <span className="live-dot" /> Live
            </>
          ) : (
            <>🕑 {formatOffset(offsetMin)}</>
          )}
        </strong>
        {!live && shownAtMs !== null && (
          <small className="sky-muted">
            {new Date(shownAtMs).toLocaleString([], {
              weekday: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </small>
        )}
        <button type="button" className="timebar__live" onClick={() => onChange(0)} disabled={live}>
          Live
        </button>
        <button
          type="button"
          className="timebar__toggle"
          aria-expanded={open}
          aria-label={open ? "Hide time travel slider" : "Show time travel slider"}
          onClick={() => setOpen(o => !o)}
        >
          {open ? "▾" : "▴"}
        </button>
      </div>

      <div className="timebar__body">

      <input
        type="range"
        min={-max}
        max={max}
        step={5}
        value={offsetMin}
        onChange={e => {
          const v = Number(e.target.value);
          onChange(Math.abs(v) < 5 ? 0 : v); // snap to live near the middle
        }}
        aria-label="Hours from now"
        aria-valuetext={formatOffset(offsetMin)}
      />
      <div className="timebar__ticks">
        <span>−{maxHours} h</span>
        <span>now</span>
        <span>+{maxHours} h</span>
      </div>
      {!live && (
        <small className="sky-muted">
          Orbits are less accurate the further from now. The “Your sky” panel stays live.
        </small>
      )}
      </div>
    </div>
  );
}
