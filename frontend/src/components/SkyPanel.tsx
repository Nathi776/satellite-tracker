import { useEffect, useRef, useState } from "react";
import { API_URL } from "../config";
import type { SatPass, VisibilityResponse, VisibleSat } from "../api";
import SkyRadar from "./SkyRadar";
import {
  SKY_TEXT,
  STATUS_STYLE,
  compassPoint,
  formatClock,
  formatDay,
  formatDuration,
  formatMag,
  relativeTime,
} from "../utils/sky";
import "./sky.css";

type Props = {
  visibility: VisibilityResponse;
  /** every satellite above the horizon, already moved to the current moment */
  sats: VisibleSat[];
  nakedEyeOnly: boolean;
  onNakedEyeOnlyChange: (value: boolean) => void;
  nowMs: number;
  /** seconds since the data last refreshed, or null if it never has */
  ageSeconds: number | null;
  stale: boolean;
  selected: string | null;
  onSelect: (name: string | null) => void;
};

const MAX_LIST = 8;
const MAX_PASSES = 6;

function Badge({ status }: { status: keyof typeof STATUS_STYLE }) {
  const s = STATUS_STYLE[status];
  return (
    <span className="sky-badge" style={{ ["--badge" as string]: s.color }} title={s.hint}>
      {s.label}
    </span>
  );
}

const REMIND_LEAD_MS = 10 * 60 * 1000;

/** In-tab reminder: only works while this page stays open (the calendar file works anywhere). */
function RemindButton({ pass, nowMs }: { pass: SatPass; nowMs: number }) {
  const [on, setOn] = useState(false);
  const riseMs = new Date(pass.rise_time_utc).getTime();
  const timer = useRef<number | null>(null);
  const supported = typeof Notification !== "undefined";

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    },
    [],
  );

  if (!supported || riseMs <= nowMs) return null;

  const toggle = async () => {
    if (on) {
      if (timer.current !== null) window.clearTimeout(timer.current);
      timer.current = null;
      setOn(false);
      return;
    }
    const permission = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
    if (permission !== "granted") return;
    const wait = Math.max(0, riseMs - REMIND_LEAD_MS - Date.now());
    timer.current = window.setTimeout(() => {
      new Notification(`${pass.name} is about to pass`, {
        body: `Rises in the ${pass.rise_direction} at ${formatClock(pass.rise_time_utc)}, peaks at ${Math.round(pass.max_elevation_deg)}°.`,
      });
      setOn(false);
    }, wait);
    setOn(true);
  };

  return (
    <button type="button" className="sky-remind" onClick={toggle} aria-pressed={on}>
      {on ? "🔔 Reminder on" : "🔔 Remind me"}
    </button>
  );
}

function PassCard({ pass, nowMs }: { pass: SatPass; nowMs: number }) {
  const seen = pass.visibility === "visible";
  return (
    <div className="sky-pass">
      <div className="sky-pass__top">
        <strong>{pass.name}</strong>
        <Badge status={pass.visibility} />
      </div>
      <div>
        {formatDay(pass.rise_time_utc)} · {formatClock(pass.rise_time_utc)}{" "}
        <small>({relativeTime(pass.rise_time_utc, nowMs)})</small>
      </div>
      <small>
        {pass.rise_direction} → {pass.set_direction} · peaks at {Math.round(pass.max_elevation_deg)}° in the{" "}
        {pass.peak_direction} · {formatDuration(pass.duration_seconds)}
      </small>
      <br />
      <small>
        {seen ? (
          <>
            Visible {formatClock(pass.visible_from_utc!)}–{formatClock(pass.visible_until_utc!)}
            {pass.magnitude !== null && <> · brightest ≈ mag {formatMag(pass.magnitude)}</>}
          </>
        ) : (
          STATUS_STYLE[pass.visibility].hint
        )}
      </small>
      <RemindButton pass={pass} nowMs={nowMs} />
    </div>
  );
}

export default function SkyPanel({
  visibility,
  sats,
  nakedEyeOnly,
  onNakedEyeOnlyChange,
  nowMs,
  ageSeconds,
  stale,
  selected,
  onSelect,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);

  const { observer } = visibility;
  const sky = SKY_TEXT[observer.sky];
  const shown = nakedEyeOnly ? sats.filter(s => s.naked_eye) : sats;
  const ranked = [...shown].sort(
    (a, b) => Number(b.naked_eye) - Number(a.naked_eye) || b.altitude_deg - a.altitude_deg,
  );
  const chosen = sats.find(s => s.name === selected) ?? null;

  const passes = visibility.next_passes
    .filter(p => !nakedEyeOnly || p.visibility === "visible")
    // hide a pass once it is over
    .filter(p => new Date(p.set_time_utc).getTime() > nowMs)
    .slice(0, MAX_PASSES);

  const emptyMessage = !observer.dark_enough
    ? "Sky too bright"
    : nakedEyeOnly
      ? "Nothing visible right now"
      : "Nothing above the horizon";

  return (
    <aside className={`sky-panel${collapsed ? " sky-panel--collapsed" : ""}`} aria-label="Your sky">
      <div className="sky-panel__head">
        <h3>🔭 Your sky</h3>
        <button
          className="sky-panel__collapse"
          onClick={() => setCollapsed(c => !c)}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Expand panel" : "Collapse panel"}
        >
          {collapsed ? "+" : "−"}
        </button>
      </div>

      {!collapsed && (
        <>
          <div className="sky-muted" style={{ marginTop: 4 }}>
            <span className="live-dot" style={{ ["--live" as string]: stale ? "#ef4444" : "#22c55e" }} />
            {stale
              ? "Connection lost, showing old data"
              : ageSeconds === null
                ? "Loading…"
                : `Live · updated ${ageSeconds < 2 ? "just now" : `${ageSeconds} s ago`}`}
          </div>

          <div className="sky-state">
            <strong>
              {sky.icon} {sky.label} · Sun {observer.sun_altitude_deg > 0 ? "+" : ""}
              {observer.sun_altitude_deg}°
            </strong>
            <small>
              {observer.dark_enough
                ? "Dark enough to see bright satellites."
                : "Too bright to see satellites. They become visible once the Sun is below −6°."}
            </small>
          </div>

          <label className="sky-toggle">
            <input
              type="checkbox"
              checked={nakedEyeOnly}
              onChange={e => onNakedEyeOnlyChange(e.target.checked)}
            />
            Naked-eye visible only
          </label>

          <SkyRadar
            sats={shown}
            selected={selected}
            onSelect={onSelect}
            emptyMessage={emptyMessage}
          />

          <div className="sky-legend">
            {(nakedEyeOnly ? (["visible"] as const) : (["visible", "faint", "in_shadow", "daylight"] as const)).map(
              k => (
                <span
                  key={k}
                  className={k === "in_shadow" ? "hollow" : undefined}
                  style={{ ["--dot" as string]: STATUS_STYLE[k].color }}
                >
                  {STATUS_STYLE[k].label}
                </span>
              ),
            )}
          </div>
          <div className="sky-muted" style={{ marginTop: 6 }}>
            Looking up: north at the top, east on the left, centre = straight overhead.
          </div>

          {chosen && (
            <div className="sky-detail">
              <div className="sky-detail__title">
                <span>{chosen.name}</span>
                <Badge status={chosen.status} />
              </div>
              <div>
                {Math.round(chosen.altitude_deg)}° above the horizon, towards{" "}
                {compassPoint(chosen.azimuth_deg)} ({Math.round(chosen.azimuth_deg)}°)
              </div>
              <small>
                Range {Math.round(chosen.distance_km).toLocaleString()} km
                {chosen.magnitude !== null && <> · est. magnitude {formatMag(chosen.magnitude)}</>}
              </small>
              <br />
              <small>{STATUS_STYLE[chosen.status].hint}</small>
            </div>
          )}

          <h4>
            {nakedEyeOnly ? "Visible now" : "Above the horizon"} ({shown.length})
          </h4>
          {ranked.length === 0 ? (
            <div className="sky-muted">
              {observer.dark_enough
                ? nakedEyeOnly
                  ? "No satellite you can see by eye is overhead right now."
                  : "No satellites are above your horizon."
                : "The sky is too bright right now."}
            </div>
          ) : (
            <ul className="sky-list">
              {ranked.slice(0, MAX_LIST).map(s => (
                <li key={s.name}>
                  <button onClick={() => onSelect(s.name === selected ? null : s.name)} title={s.name}>
                    <strong>{s.name}</strong> <small className="sky-muted">{Math.round(s.altitude_deg)}° {compassPoint(s.azimuth_deg)}</small>
                  </button>
                  <Badge status={s.status} />
                </li>
              ))}
            </ul>
          )}
          {ranked.length > MAX_LIST && (
            <div className="sky-muted">+ {ranked.length - MAX_LIST} more on the radar</div>
          )}

          <h4>Next passes · 48 h</h4>
          <a
            className="sky-calendar"
            href={`${API_URL}/passes/calendar.ics?lat=${observer.lat}&lon=${observer.lon}&hours=48&naked_eye_only=${nakedEyeOnly}`}
            download="satellite-passes.ics"
          >
            📅 Add {nakedEyeOnly ? "visible" : "all"} passes to my calendar
          </a>
          {passes.length === 0 ? (
            <div className="sky-muted">
              {nakedEyeOnly
                ? "No naked-eye passes in the next 48 hours. Untick the filter to see every pass."
                : "No passes above 10° in the next 48 hours."}
            </div>
          ) : (
            passes.map(p => <PassCard key={`${p.name}-${p.rise_time_utc}`} pass={p} nowMs={nowMs} />)
          )}
        </>
      )}
    </aside>
  );
}
