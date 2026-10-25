export const EARTH_RADIUS_KM = 6371;

type LatLon = [number, number];

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

/** Wrap a longitude into [-180, 180). */
export const normalizeLon = (lon: number) => ((((lon + 180) % 360) + 360) % 360) - 180;

/** Great-circle distance between two points, in km. */
export function distanceKm(a: LatLon, b: LatLon): number {
  const [lat1, lon1] = [rad(a[0]), rad(a[1])];
  const [lat2, lon2] = [rad(b[0]), rad(b[1])];
  const h =
    Math.sin((lat2 - lat1) / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 * The circle of points `radiusKm` away from (lat, lon), as polygons Leaflet can draw.
 *
 * A circle on the globe is awkward on a flat map in two cases, both handled here:
 *  - it crosses the date line: the ring keeps continuous (unwrapped) longitudes and is
 *    returned three times, shifted by -360, 0 and +360 degrees, so it shows on whichever
 *    copy of the world the user is looking at;
 *  - it contains a pole (high-latitude satellites with a big footprint): the outline
 *    then runs the whole way round the Earth, so it is closed along the pole instead.
 */
export function footprintPolygons(
  lat: number,
  lon: number,
  radiusKm: number,
  steps = 96,
): LatLon[][] {
  if (!(radiusKm > 0) || !Number.isFinite(lat) || !Number.isFinite(lon)) return [];

  const angle = Math.min(radiusKm / EARTH_RADIUS_KM, Math.PI - 1e-6); // angular radius
  const phi = rad(lat);

  const ring: LatLon[] = [];
  for (let i = 0; i < steps; i++) {
    const bearing = (2 * Math.PI * i) / steps;
    const phi2 = Math.asin(
      Math.sin(phi) * Math.cos(angle) + Math.cos(phi) * Math.sin(angle) * Math.cos(bearing),
    );
    const dLon = Math.atan2(
      Math.sin(bearing) * Math.sin(angle) * Math.cos(phi),
      Math.cos(angle) - Math.sin(phi) * Math.sin(phi2),
    );
    ring.push([deg(phi2), lon + deg(dLon)]);
  }

  const containsPole = Math.abs(lat) + deg(angle) >= 90;
  if (containsPole) {
    const poleLat = lat >= 0 ? 90 : -90;
    const edge = ring
      .map(([la, lo]): LatLon => [la, normalizeLon(lo)])
      .sort((a, b) => a[1] - b[1]);
    return [[[poleLat, -180], ...edge, [poleLat, 180]]];
  }

  return [-360, 0, 360].map(shift => ring.map(([la, lo]): LatLon => [la, lo + shift]));
}
