/** Split a ground track where it wraps across the ±180° meridian, so Leaflet
 *  doesn't draw a line straight across the whole map. */
export function splitTrack(points: number[][]) {
  if (points.length === 0) return [];

  const segments: number[][][] = [];
  let current: number[][] = [points[0]];

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const curr = points[i];

    if (Math.abs(curr[1] - prev[1]) > 180) {
      segments.push(current);
      current = [];
    }
    current.push(curr);
  }

  if (current.length) segments.push(current);
  return segments;
}
