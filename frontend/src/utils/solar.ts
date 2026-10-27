import { EARTH_RADIUS_KM, footprintPolygons, normalizeLon } from "./geo";

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;
const mod360 = (d: number) => ((d % 360) + 360) % 360;

/**
 * The point on Earth where the Sun is straight overhead (NOAA low-precision formulas,
 * accurate to about 0.01 degrees, which is far finer than the map can show).
 */
export function subsolarPoint(timeMs: number): { lat: number; lon: number } {
  const n = timeMs / 86_400_000 + 2440587.5 - 2451545.0; // days since J2000
  const meanLon = mod360(280.46 + 0.9856474 * n);
  const anomaly = rad(mod360(357.528 + 0.9856003 * n));
  const lambda = rad(meanLon + 1.915 * Math.sin(anomaly) + 0.02 * Math.sin(2 * anomaly));
  const eps = rad(23.439 - 0.0000004 * n);

  const ra = Math.atan2(Math.cos(eps) * Math.sin(lambda), Math.cos(lambda));
  const dec = Math.asin(Math.sin(eps) * Math.sin(lambda));
  const gmst = mod360(280.46061837 + 360.98564736629 * n);

  return { lat: deg(dec), lon: normalizeLon(deg(ra) - gmst) };
}

/** Sun-altitude thresholds (degrees) of the shaded bands: night, civil, nautical, astronomical. */
export const TWILIGHT_LEVELS = [0, -6, -12, -18] as const;

/**
 * Where the Sun is below `altitudeDeg`, as map polygons.
 *
 * Seen from the Sun's antipode, the region where the Sun is lower than `a` is a circle
 * (a spherical cap) of angular radius 90 + a degrees. So each band is just a circle drawn
 * around the anti-solar point, which the footprint helper already knows how to draw across
 * the date line and over the poles.
 */
export function nightPolygons(timeMs: number, altitudeDeg: number): [number, number][][] {
  const sun = subsolarPoint(timeMs);
  const antiLat = -sun.lat;
  const antiLon = normalizeLon(sun.lon + 180);
  const radiusDeg = 90 + altitudeDeg;

  const polar = polarCapPolygon(antiLat, antiLon, radiusDeg);
  if (polar) return [-360, 0, 360].map(shift => polar.map(([la, lo]): [number, number] => [la, lo + shift]));

  return footprintPolygons(antiLat, antiLon, rad(radiusDeg) * EARTH_RADIUS_KM, 120);
}

/**
 * A circle (centre lat/lon, angular radius) that contains a pole, as ONE polygon spanning
 * longitude -180..180 and closed along that pole. Its edge is solved exactly at every degree
 * of longitude, including +-180, so copies shifted by 360 degrees meet with no gap.
 * Returns null when the circle contains neither pole.
 */
export function polarCapPolygon(
  centreLat: number,
  centreLon: number,
  radiusDeg: number,
): [number, number][] | null {
  const phi0 = rad(centreLat);
  const cosR = Math.cos(rad(radiusDeg));
  const eps = 1e-9;
  const northIn = 90 - centreLat <= radiusDeg + eps;
  const southIn = 90 + centreLat <= radiusDeg + eps;
  if (!northIn && !southIn) return null;
  const inPole = northIn ? 90 : -90;
  const outPole = -inPole;

  // cos(distance from centre) at latitude phi on the meridian dLon away from the centre
  const closeness = (phi: number, dLon: number) =>
    Math.sin(phi) * Math.sin(phi0) + Math.cos(phi) * Math.cos(phi0) * Math.cos(dLon);

  const edge: [number, number][] = [];
  for (let lon = -180; lon <= 180; lon += 1) {
    const dLon = rad(lon - centreLon);
    let lo = rad(inPole); // inside the circle
    let hi = rad(outPole); // outside it (if the other pole is inside too, the edge is at the far pole)
    if (closeness(hi, dLon) >= cosR) {
      edge.push([outPole, lon]);
      continue;
    }
    for (let i = 0; i < 40; i++) {
      const mid = (lo + hi) / 2;
      if (closeness(mid, dLon) >= cosR) lo = mid;
      else hi = mid;
    }
    edge.push([deg((lo + hi) / 2), lon]);
  }
  return [[inPole, -180], ...edge, [inPole, 180]];
}
