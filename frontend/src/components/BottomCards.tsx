import type { SatPass, VisibleSat } from "../api";
import { STATUS_STYLE, compassPoint, relativeTime } from "../utils/sky";
import SkyRadar from "./SkyRadar";
import type { SkyTab } from "./SkyPanel";
import "./bottom-cards.css";

type Props = {
  /** every satellite above the horizon, moved to this moment */
  sats: VisibleSat[];
  passes: SatPass[];
  nowMs: number;
  selected: string | null;
  onSelect: (name: string) => void;
  onViewAll: (tab: SkyTab) => void;
};

const ROWS = 5;
const fmtKm = (km: number) => Math.round(km).toLocaleString();

/** Desktop: three at-a-glance cards under the map. */
export default function BottomCards({ sats, passes, nowMs, selected, onSelect, onViewAll }: Props) {
  const ranked = [...sats].sort(
    (a, b) => Number(b.naked_eye) - Number(a.naked_eye) || b.altitude_deg - a.altitude_deg,
  );
  const upcoming = passes.filter(p => new Date(p.set_time_utc).getTime() > nowMs).slice(0, ROWS);
  const chosen = sats.find(s => s.name === selected) ?? null;

  return (
    <section className="bottom-cards" aria-label="Summary of your sky">
      <article className="card">
        <header>
          <h3>Visible satellites <small>(from your location)</small></h3>
          <button type="button" onClick={() => onViewAll("now")}>View all</button>
        </header>
        {ranked.length === 0 ? (
          <p className="card__empty">No satellites are above your horizon right now.</p>
        ) : (
          <table>
            <thead>
              <tr><th /><th>Satellite</th><th>Elevation</th><th>Azimuth</th><th>Distance</th></tr>
            </thead>
            <tbody>
              {ranked.slice(0, ROWS).map(s => (
                <tr key={s.name} className={s.name === selected ? "is-selected" : undefined}>
                  <td>
                    <span
                      className="dot"
                      title={STATUS_STYLE[s.status].label}
                      style={{ ["--dot" as string]: STATUS_STYLE[s.status].color }}
                    />
                  </td>
                  <td>
                    <button type="button" onClick={() => onSelect(s.name)} title={s.name}>{s.name}</button>
                  </td>
                  <td>{s.altitude_deg.toFixed(1)}°</td>
                  <td>{s.azimuth_deg.toFixed(1)}°</td>
                  <td>{fmtKm(s.distance_km)} km</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </article>

      <article className="card">
        <header>
          <h3>Next passes</h3>
          <button type="button" onClick={() => onViewAll("passes")}>View all</button>
        </header>
        {upcoming.length === 0 ? (
          <p className="card__empty">No passes above 10° in the next 48 hours.</p>
        ) : (
          <table>
            <thead>
              <tr><th /><th>Satellite</th><th>Starts</th><th>Max elevation</th></tr>
            </thead>
            <tbody>
              {upcoming.map(p => (
                <tr key={`${p.name}-${p.rise_time_utc}`}>
                  <td>
                    <span
                      className="dot"
                      title={STATUS_STYLE[p.visibility].label}
                      style={{ ["--dot" as string]: STATUS_STYLE[p.visibility].color }}
                    />
                  </td>
                  <td>
                    <button type="button" onClick={() => onSelect(p.name)} title={p.name}>{p.name}</button>
                  </td>
                  <td>{relativeTime(p.rise_time_utc, nowMs)}</td>
                  <td>{p.max_elevation_deg.toFixed(1)}°</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </article>

      <article className="card card--compass">
        <header>
          <h3>Sky compass</h3>
        </header>
        <div className="compass">
          <SkyRadar sats={sats} selected={selected} onSelect={n => n && onSelect(n)} size={168} />
          <dl>
            {chosen ? (
              <>
                <dt>{chosen.name}</dt>
                <dd>{Math.round(chosen.azimuth_deg)}° {compassPoint(chosen.azimuth_deg)}</dd>
                <dt>Elevation</dt>
                <dd>{chosen.altitude_deg.toFixed(1)}°</dd>
              </>
            ) : (
              <>
                <dt>Above horizon</dt>
                <dd>{sats.length}</dd>
                <dt>Visible by eye</dt>
                <dd>{sats.filter(s => s.naked_eye).length}</dd>
              </>
            )}
          </dl>
        </div>
      </article>
    </section>
  );
}
