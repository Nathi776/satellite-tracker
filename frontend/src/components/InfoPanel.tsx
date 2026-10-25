import type { SatellitePos } from "../api";
import { groupColor } from "../utils/groups";
import "./map-ui.css";

type Props = {
  satellite: SatellitePos | null;
  /** human label for the satellite's group, e.g. "Stations" */
  groupLabel?: string;
  onClose: () => void;
};

const fmtKm = (km: number) => Math.round(km).toLocaleString();

function period(min: number): string {
  if (min >= 90 * 12) return `${(min / 60).toFixed(1)} h`;
  return `${min.toFixed(1)} min`;
}

export default function InfoPanel({ satellite, groupLabel, onClose }: Props) {
  if (!satellite) return null;
  const { lat, lon, alt_km, speed_kms, period_min, footprint_km } = satellite;

  return (
    <section className="info" aria-label={`Details for ${satellite.name}`}>
      <div className="info__head">
        <h3 title={satellite.name}>{satellite.name}</h3>
        <button type="button" className="info__close" onClick={onClose} aria-label="Close details">
          ×
        </button>
      </div>

      {groupLabel && (
        <span className="info__group" style={{ ["--chip" as string]: groupColor(satellite.group) }}>
          {groupLabel}
        </span>
      )}

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
    </section>
  );
}
