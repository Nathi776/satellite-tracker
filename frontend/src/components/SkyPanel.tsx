import { useState } from "react";
import { API_URL } from "../config";
import type { VisibilityResponse, VisibleSat } from "../api";
import SkyRadar from "./SkyRadar";
import AfricaPasses from "./AfricaPasses";
import SkyVerdict from "./SkyVerdict";
import SkyView from "./SkyView";
import { Badge, PassCard } from "./PassCard";
import {
  SKY_TEXT,
  STATUS_STYLE,
  compassPoint,
  formatMag,
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

type Tab = "now" | "passes" | "africa";
const TABS: { id: Tab; label: string }[] = [
  { id: "now", label: "Now" },
  { id: "passes", label: "Passes" },
  { id: "africa", label: "🌍 Africa" },
];

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
  const [tab, setTab] = useState<Tab>("now");
  const [viewOpen, setViewOpen] = useState(false);

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
          <div className="sky-status">
            <span className="live-dot" style={{ ["--live" as string]: stale ? "#ef4444" : "#22c55e" }} />
            <span title={observer.dark_enough ? "Dark enough to see bright satellites." : "Satellites are visible once the Sun is below −6°."}>
              {sky.icon} {sky.label}
              {observer.dark_enough ? " · dark enough" : " · too bright"}
            </span>
            <small className="sky-muted">
              {stale
                ? "offline, old data"
                : ageSeconds === null
                  ? "loading…"
                  : ageSeconds < 2
                    ? "live"
                    : `${ageSeconds} s ago`}
            </small>
          </div>

          <SkyVerdict
            sats={sats}
            passes={visibility.next_passes}
            nowMs={nowMs}
            darkEnough={observer.dark_enough}
            onSelect={name => {
              onSelect(name);
              setTab("now");
            }}
          />

          <div className="sky-tabs" role="tablist" aria-label="Sky sections">
            {TABS.map(t => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                className={tab === t.id ? "is-active" : undefined}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab !== "africa" && (
            <label className="sky-toggle">
              <input
                type="checkbox"
                checked={nakedEyeOnly}
                onChange={e => onNakedEyeOnlyChange(e.target.checked)}
              />
              Naked-eye visible only
            </label>
          )}

          {tab === "now" && (
            <>
              <button type="button" className="sky-viewbtn" onClick={() => setViewOpen(true)}>
                📱 Open sky view <small>(point your phone at the sky)</small>
              </button>
              <SkyRadar sats={shown} selected={selected} onSelect={onSelect} emptyMessage={emptyMessage} />
              <div className="sky-muted sky-caption">
                North at the top, east on the left, centre = straight overhead.
              </div>
              {!nakedEyeOnly && (
                <div className="sky-legend">
                  {(["visible", "faint", "in_shadow", "daylight"] as const).map(k => (
                    <span
                      key={k}
                      className={k === "in_shadow" ? "hollow" : undefined}
                      style={{ ["--dot" as string]: STATUS_STYLE[k].color }}
                    >
                      {STATUS_STYLE[k].label}
                    </span>
                  ))}
                </div>
              )}

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
                        <strong>{s.name}</strong>{" "}
                        <small className="sky-muted">
                          {Math.round(s.altitude_deg)}° {compassPoint(s.azimuth_deg)}
                        </small>
                      </button>
                      <Badge status={s.status} />
                    </li>
                  ))}
                </ul>
              )}
              {ranked.length > MAX_LIST && (
                <div className="sky-muted">+ {ranked.length - MAX_LIST} more on the radar</div>
              )}
            </>
          )}

          {tab === "passes" && (
            <>
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

          {tab === "africa" && <AfricaPasses lat={observer.lat} lon={observer.lon} nowMs={nowMs} />}
        </>
      )}
      {viewOpen && (
        <SkyView
          sats={shown}
          selected={selected}
          onSelect={onSelect}
          onClose={() => setViewOpen(false)}
          declinationDeg={observer.declination_deg ?? 0}
        />
      )}
    </aside>
  );
}
