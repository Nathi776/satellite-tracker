import { API_URL } from "./config";

export type SatellitePos = {
  name: string;
  lat: number;
  lon: number;
  alt_km?: number;
  speed_kms?: number;
  period_min?: number | null;
};

export type VisibleSat = {
  name: string;
  lat: number;
  lon: number;
  altitude_deg: number;
  azimuth_deg: number;
  distance_km: number;
};

export type SatPass = {
  name: string;
  rise_time_utc: string;
  peak_time_utc: string;
  set_time_utc: string;
  rise_azimuth_deg: number;
  peak_azimuth_deg: number;
  set_azimuth_deg: number;
  max_elevation_deg: number;
};

export type VisibilityResponse = {
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

export const fetchPositions = (search: string, signal?: AbortSignal) =>
  getJson<SatellitePos[]>(`/positions?search=${encodeURIComponent(search)}`, signal);

export const fetchVisibility = (lat: number, lon: number, signal?: AbortSignal) =>
  getJson<VisibilityResponse>(`/observer/visibility?lat=${lat}&lon=${lon}`, signal);

export const fetchGroundTrack = (name: string, signal?: AbortSignal) =>
  getJson<{ satellite: string; track: TrackPoint[] }>(
    `/groundtrack/${encodeURIComponent(name)}`,
    signal,
  );
