import { API_URL } from "./config";

export type SatellitePos = {
  name: string;
  lat: number;
  lon: number;
  alt_km?: number;
  speed_kms?: number;
  period_min?: number | null;
  /** degrees per second, used to animate the marker between refreshes */
  lat_rate?: number;
  lon_rate?: number;
  /** satellite group id, see /groups */
  group?: string;
  /** African satellites only: the operating country, or "Pan-African" */
  country?: string | null;
  /** radius of the area on the ground that can see this satellite (horizon to horizon) */
  footprint_km?: number;
};

export type GroupInfo = { id: string; label: string; count: number };

/** Why a satellite above the horizon can or can't be seen. */
export type VisibilityStatus = "visible" | "faint" | "in_shadow" | "daylight";

export type VisibleSat = {
  name: string;
  lat: number;
  lon: number;
  altitude_deg: number;
  azimuth_deg: number;
  distance_km: number;
  sunlit: boolean;
  /** estimated apparent magnitude; null when we have no brightness data for this object */
  magnitude: number | null;
  naked_eye: boolean;
  status: VisibilityStatus;
  /** degrees per second */
  altitude_rate: number;
  azimuth_rate: number;
  lat_rate: number;
  lon_rate: number;
};

export type SatPass = {
  name: string;
  rise_time_utc: string;
  peak_time_utc: string;
  set_time_utc: string;
  rise_azimuth_deg: number;
  peak_azimuth_deg: number;
  set_azimuth_deg: number;
  rise_direction: string;
  peak_direction: string;
  set_direction: string;
  max_elevation_deg: number;
  duration_seconds: number;
  visibility: VisibilityStatus;
  visible_from_utc: string | null;
  visible_until_utc: string | null;
  visible_seconds: number;
  magnitude: number | null;
  sun_altitude_deg: number;
  sunlit_at_peak: boolean;
};

/** Where to look for one satellite from the observer, even if it is below the horizon. */
export type SatelliteView = {
  name: string;
  generated_at: string;
  sky: SkyState;
  look: VisibleSat & { above_horizon: boolean; direction: string };
  next_pass: SatPass | null;
  /** the next few passes, soonest first (the first is `next_pass`) */
  passes: SatPass[];
};

export type AfricaPass = SatPass & { country: string | null };

export type SkyState =
  | "day"
  | "twilight_civil"
  | "twilight_nautical"
  | "twilight_astronomical"
  | "night";

export type VisibilityResponse = {
  generated_at: string;
  /** how old the computation already was when the server sent it */
  age_seconds: number;
  observer: {
    lat: number;
    lon: number;
    sun_altitude_deg: number;
    sky: SkyState;
    dark_enough: boolean;
    /** magnetic declination in degrees, east positive; null if unavailable */
    declination_deg?: number | null;
  };
  visible_now: VisibleSat[];
  next_passes: SatPass[];
};

export type TrackPoint = { lat: number; lon: number };

/** GET helper that throws on HTTP errors (fetch alone only rejects on network failure). */
async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body wasn't JSON */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const fetchGroups = (signal?: AbortSignal) => getJson<GroupInfo[]>("/groups", signal);

const isoTime = (ms: number) => encodeURIComponent(new Date(ms).toISOString());

export type SatelliteInfo = {
  name: string;
  norad_id: number;
  group: string;
  country: string | null;
  description: string;
  inclination_deg: number;
  eccentricity: number;
  period_min: number;
  revs_per_day: number;
  perigee_km: number;
  apogee_km: number;
  epoch_utc: string;
  element_age_days: number;
};

export type PositionsQuery = {
  /** exact satellite names (favourites); overrides search, group and limit */
  names?: string[];
  search?: string;
  group?: string;
  limit?: number;
  /** show positions at this time (ms since epoch) instead of now */
  at?: number | null;
};

export const fetchPositions = (q: PositionsQuery, signal?: AbortSignal) => {
  const params = [`search=${encodeURIComponent(q.search ?? "")}`];
  for (const n of q.names ?? []) params.push(`names=${encodeURIComponent(n)}`);
  if (q.group && q.group !== "all") params.push(`group=${encodeURIComponent(q.group)}`);
  if (q.limit) params.push(`limit=${q.limit}`);
  if (q.at) params.push(`at=${isoTime(q.at)}`);
  return getJson<SatellitePos[]>(`/positions?${params.join("&")}`, signal);
};

export const fetchVisibility = (
  lat: number,
  lon: number,
  hours = 48,
  signal?: AbortSignal,
) =>
  getJson<VisibilityResponse>(
    `/observer/visibility?lat=${lat}&lon=${lon}&hours=${hours}`,
    signal,
  );

export const fetchGroundTrack = (
  name: string,
  opts: { at?: number | null; minutes?: number; step?: number } = {},
  signal?: AbortSignal,
) => {
  const params: string[] = [];
  if (opts.minutes) params.push(`minutes=${opts.minutes}`);
  if (opts.step) params.push(`step=${opts.step}`);
  if (opts.at) params.push(`at=${isoTime(opts.at)}`);
  const query = params.length ? `?${params.join("&")}` : "";
  return getJson<{ satellite: string; track: TrackPoint[] }>(
    `/groundtrack/${encodeURIComponent(name)}${query}`,
    signal,
  );
};

export const fetchAfricaPasses = (lat: number, lon: number, hours = 24, signal?: AbortSignal) =>
  getJson<{ hours: number; passes: AfricaPass[] }>(
    `/africa/passes?lat=${lat}&lon=${lon}&hours=${hours}`,
    signal,
  );

export const fetchSatelliteView = (
  name: string,
  lat: number,
  lon: number,
  signal?: AbortSignal,
) =>
  getJson<SatelliteView>(
    `/satellite/${encodeURIComponent(name)}/view?lat=${lat}&lon=${lon}&hours=48`,
    signal,
  );

export const fetchSatelliteInfo = (name: string, signal?: AbortSignal) =>
  getJson<SatelliteInfo>(`/satellite/${encodeURIComponent(name)}/info`, signal);

export const fetchSatellitePosition = (name: string, signal?: AbortSignal) =>
  getJson<{ name: string; position: Omit<SatellitePos, "name"> }>(
    `/satellite/${encodeURIComponent(name)}`,
    signal,
  );
