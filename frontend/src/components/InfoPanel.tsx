import type { SatelliteView, SatellitePos } from "../api";
import { groupColor } from "../utils/groups";
import { compassPoint as compass, formatClock, formatDay, formatDuration, formatMag, relativeTime } from "../utils/sky";
import { Badge } from "./PassCard";
import { satelliteHref } from "../hooks/useHashRoute";
import "./map-ui.css";

type Props = {
  satellite: SatellitePos | null;
  /** has the user shared a location (needed for "where to look") */
  hasLocation?: boolean;
  /** the map shows another moment: where-to-look is only available live */
  timeTravel?: boolean;
  view?: SatelliteView | null;
  /** Date.now() when `view` arrived, so its rates can move it along */
  viewReceivedAt?: number | null;
  nowMs?: number;
  /** ground-track toggle (desktop card); omit to hide it */
  favourite?: boolean;
  onToggleFavourite?: (name: string) => void;
  showTrack?: boolean;
  onShowTrackChange?: (on: boolean) => void;
  /** human label for the satellite's group, e.g. "Stations" */
  groupLabel?: string;
  onClose: () => void;
};

const fmtKm = (km: number) => Math.round(km).toLocaleString();

function period(min: number): string {
  if (min >= 90 * 12) return `${(min / 60).toFixed(1)} h`;
  return `${min.toFixed(1)} min`;
}

/** Where to look, from the observer: the server's numbers moved along by their per-second rates. */
export function WhereToLook({ view, receivedAt, nowMs }: { view: SatelliteView; receivedAt: number | null; nowMs: number }) {
  const { look } = view;
  const elapsed = receivedAt ? Math.max(0, (nowMs - receivedAt) / 1000) : 0;
  const el = look.altitude_deg + look.altitude_rate * elapsed;
  const az = (((look.azimuth_deg + look.azimuth_rate * elapsed) % 360) + 360) % 360;
  const up = el > 0;
  const pass = view.next_pass;

  return (
    <div className="info__look">
      <h4>From where you are</h4>
      {up ? (
        <p className="info__headline">
          <strong>{Math.round(el)}° up</strong>, towards the <strong>{compass(az)}</strong>
        </p>
      ) : (
        <p className="info__headline info__headline--down">
          Below your horizon <small>(−{Math.abs(Math.round(el))}°)</small>
        </p>
      )}
      <dl className="info__grid">
        <dt>Azimuth</dt>
        <dd>
          {Math.round(az)}° {compass(az)}
        </dd>
        <dt>Elevation</dt>
        <dd>{el < 0 ? "−" : ""}{Math.abs(el).toFixed(1)}°</dd>
        <dt>Distance</dt>
        <dd>{fmtKm(look.distance_km)} km</dd>
        {up && (
          <>
            <dt>Can you see it?</dt>
            <dd>
              <Badge status={look.status} />
              {look.magnitude !== null && <small> mag {formatMag(look.magnitude)}</small>}
            </dd>
          </>
        )}
        <dt>Next pass</dt>
        <dd>
          {pass ? (
            <>
              {formatDay(pass.rise_time_utc)} {formatClock(pass.rise_time_utc)}{" "}
              <small>({relativeTime(pass.rise_time_utc, nowMs)})</small>
              <br />
              <small>
                {pass.rise_direction} → {pass.set_direction} · peaks at {Math.round(pass.max_elevation_deg)}° ·{" "}
                {formatDuration(pass.duration_seconds)} · <Badge status={pass.visibility} />
              </small>
            </>
          ) : (
            <small>none above 10° in the next 48 h</small>
          )}
        </dd>
      </dl>
    </div>
  );
}

export default function InfoPanel({
  satellite,
  hasLocation = false,
  timeTravel = false,
  view = null,
  viewReceivedAt = null,
  nowMs = Date.now(),
  favourite = false,
  onToggleFavourite,
  showTrack,
  onShowTrackChange,
  groupLabel,
  onClose,
}: Props) {
  if (!satellite) return null;
  const { lat, lon, alt_km, speed_kms, period_min, footprint_km } = satellite;

  return (
    <section className="info" aria-label={`Details for ${satellite.name}`}>
      <div className="info__head">
        <h3 title={satellite.name}>{satellite.name}</h3>
        {view?.look.above_horizon && !timeTravel && <Badge status={view.look.status} />}
        {onToggleFavourite && (
          <button
            type="button"
            className={`info__star${favourite ? " is-on" : ""}`}
            aria-pressed={favourite}
            aria-label={favourite ? "Remove from favourites" : "Add to favourites"}
            title={favourite ? "Remove from favourites" : "Add to favourites"}
            onClick={() => onToggleFavourite(satellite.name)}
          >
            {favourite ? "★" : "☆"}
          </button>
        )}
        <button type="button" className="info__close" onClick={onClose} aria-label="Close details">
          ×
        </button>
      </div>

      {groupLabel && (
        <span className="info__group" style={{ ["--chip" as string]: groupColor(satellite.group) }}>
          {groupLabel}
          {satellite.country ? ` · ${satellite.country}` : ""}
        </span>
      )}

      {!hasLocation ? (
        <p className="info__note">📍 Use My Location to see where to look for this satellite and when it passes.</p>
      ) : timeTravel ? (
        <p className="info__note">Where to look is only shown for the live sky. Press Live to see it.</p>
      ) : view ? (
        <WhereToLook view={view} receivedAt={viewReceivedAt} nowMs={nowMs} />
      ) : (
        <p className="info__note">Working out where to look…</p>
      )}

      {onShowTrackChange && (
        <label className="info__track">
          Show orbit track
          <input
            type="checkbox"
            role="switch"
            checked={!!showTrack}
            onChange={e => onShowTrackChange(e.target.checked)}
          />
        </label>
      )}

      <details className="info__more">
        <summary>Orbit details</summary>
      <dl className="info__grid">
        <dt>Over</dt>
        <dd>
          {Math.abs(lat).toFixed(2)}° {lat >= 0 ? "N" : "S"}, {Math.abs(lon).toFixed(2)}° {lon >= 0 ? "E" : "W"}
        </dd>

        {alt_km !== undefined && (
          <>
            <dt>Altitude</dt>
            <dd>{fmtKm(alt_km)} km</dd>
          </>
        )}
        {speed_kms !== undefined && (
          <>
            <dt>Speed</dt>
            <dd>
              {speed_kms.toFixed(2)} km/s <small>({Math.round(speed_kms * 3600).toLocaleString()} km/h)</small>
            </dd>
          </>
        )}
        {period_min != null && (
          <>
            <dt>Orbit</dt>
            <dd>{period(period_min)}</dd>
          </>
        )}
        {footprint_km != null && footprint_km > 0 && (
          <>
            <dt>Sees</dt>
            <dd>
              within {fmtKm(footprint_km)} km <small>(shaded circle)</small>
            </dd>
          </>
        )}
      </dl>
      </details>

      <a className="info__details" href={satelliteHref(satellite.name)}>
        View details →
      </a>
    </section>
  );
}
