import { useEffect, useRef, useState } from "react";
import type { SatPass } from "../api";
import { STATUS_STYLE, formatClock, formatDay, formatDuration, formatMag, relativeTime } from "../utils/sky";

export function Badge({ status }: { status: keyof typeof STATUS_STYLE }) {
  const s = STATUS_STYLE[status];
  return (
    <span className="sky-badge" style={{ ["--badge" as string]: s.color }} title={s.hint}>
      {s.label}
    </span>
  );
}

const REMIND_LEAD_MS = 10 * 60 * 1000;

/** In-tab reminder: only works while this page stays open (the calendar file works anywhere). */
export function RemindButton({ pass, nowMs }: { pass: SatPass; nowMs: number }) {
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

export function PassCard({ pass, nowMs }: { pass: SatPass; nowMs: number }) {
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
            {pass.magnitude !== null && <> · brightest · mag {formatMag(pass.magnitude, pass.magnitude_source)}</>}
          </>
        ) : (
          STATUS_STYLE[pass.visibility].hint
        )}
      </small>
      <RemindButton pass={pass} nowMs={nowMs} />
    </div>
  );
}

