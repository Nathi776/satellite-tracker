import type {
  SatellitePos,
  SkyState,
  VisibilityStatus,
  VisibleSat,
} from "../api";

// ---------------------------------------------------------------------------
// Live motion: the API refreshes every few seconds and returns each object's
// per-second rates, so between refreshes we move it along linearly.
// Over ~10 s the error is well under 1 km of position.
// ---------------------------------------------------------------------------
export const wrapLon = (lon: number) => ((((lon + 180) % 360) + 360) % 360) - 180;

export function moveOnMap<T extends SatellitePos>(sat: T, elapsedS: number): T {
  if (sat.lat_rate === undefined || sat.lon_rate === undefined) return sat;
  return {
    ...sat,
    lat: Math.max(-90, Math.min(90, sat.lat + sat.lat_rate * elapsedS)),
    lon: wrapLon(sat.lon + sat.lon_rate * elapsedS),
  };
}

/** Move a satellite through the sky. Returns null once it has dropped below the horizon. */
export function moveInSky(sat: VisibleSat, elapsedS: number): VisibleSat | null {
  const altitude = sat.altitude_deg + sat.altitude_rate * elapsedS;
  if (altitude <= 0) return null;
  return {
    ...sat,
    altitude_deg: altitude,
    azimuth_deg: (((sat.azimuth_deg + sat.azimuth_rate * elapsedS) % 360) + 360) % 360,
    lat: Math.max(-90, Math.min(90, sat.lat + sat.lat_rate * elapsedS)),
    lon: wrapLon(sat.lon + sat.lon_rate * elapsedS),
  };
}

// ---------------------------------------------------------------------------
// Directions
// ---------------------------------------------------------------------------
const POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];

export const compassPoint = (az: number) =>
  POINTS[Math.floor((((az % 360) + 360) % 360 + 11.25) / 22.5) % 16];

// ---------------------------------------------------------------------------
// Text
// ---------------------------------------------------------------------------
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  if (s < 90) return `${s} s`;
  const m = Math.round(s / 60);
  if (m < 90) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h} h ${rest} min` : `${h} h`;
}

export const formatMag = (m: number | null) =>
  m === null ? "–" : `${m > 0 ? "+" : m < 0 ? "−" : ""}${Math.abs(m).toFixed(1)}`;

export const formatClock = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export const formatDay = (iso: string) =>
  new Date(iso).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });

export const SKY_TEXT: Record<SkyState, { icon: string; label: string }> = {
  day: { icon: "☀️", label: "Daylight" },
  twilight_civil: { icon: "🌇", label: "Civil twilight" },
  twilight_nautical: { icon: "🌆", label: "Nautical twilight" },
  twilight_astronomical: { icon: "🌃", label: "Astronomical twilight" },
  night: { icon: "🌙", label: "Night" },
};

export const STATUS_STYLE: Record<
  VisibilityStatus,
  { color: string; label: string; hint: string }
> = {
  visible: {
    color: "#22c55e",
    label: "Visible",
    hint: "Dark sky, in sunlight and bright enough to see without a telescope",
  },
  faint: {
    color: "#f59e0b",
    label: "Too faint",
    hint: "Sunlit on a dark sky, but too faint, too low or of unknown brightness",
  },
  in_shadow: {
    color: "#8b93a7",
    label: "In shadow",
    hint: "Inside Earth's shadow, so there is no sunlight to reflect",
  },
  daylight: {
    color: "#60a5fa",
    label: "Daylight",
    hint: "The sky is too bright to see it",
  },
};

/** "in 2 h 15 min" / "now" / "12 min ago" relative to `nowMs`. */
export function relativeTime(iso: string, nowMs: number): string {
  const diffS = (new Date(iso).getTime() - nowMs) / 1000;
  if (Math.abs(diffS) < 30) return "now";
  return diffS > 0 ? `in ${formatDuration(diffS)}` : `${formatDuration(-diffS)} ago`;
}
