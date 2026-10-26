/**
 * Where is a phone pointing, and where on its screen does a satellite appear?
 *
 * Frames (right-handed):
 *   device: x to the right of the screen, y to the top of the screen, z out of the screen.
 *           The rear camera looks along -z.
 *   world:  x east, y north, z up.
 * The browser's DeviceOrientation event gives alpha (rotation about z, counter-clockwise from
 * north), beta (about x) and gamma (about y) and the device-to-world rotation is
 * R = Rz(alpha) · Rx(beta) · Ry(gamma) (W3C DeviceOrientation spec, section 4.1).
 *
 * Only portrait use is supported.
 */

export type Vec3 = [number, number, number];
export type Basis = { forward: Vec3; right: Vec3; up: Vec3 };

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

export const normalizeDeg = (d: number) => ((d % 360) + 360) % 360;
export const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

function norm(v: Vec3): Vec3 {
  const n = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / n, v[1] / n, v[2] / n];
}

/** The device's right / up / camera-forward directions in the world frame. */
export function deviceBasis(alphaDeg: number, betaDeg: number, gammaDeg: number): Basis {
  const a = rad(alphaDeg), b = rad(betaDeg), g = rad(gammaDeg);
  const ca = Math.cos(a), sa = Math.sin(a);
  const cb = Math.cos(b), sb = Math.sin(b);
  const cg = Math.cos(g), sg = Math.sin(g);
  // columns of R = Rz(a) Rx(b) Ry(g): where the device's x, y, z axes point in the world
  const x: Vec3 = [ca * cg - sa * sb * sg, sa * cg + ca * sb * sg, -cb * sg];
  const y: Vec3 = [-sa * cb, ca * cb, sb];
  const z: Vec3 = [ca * sg + sa * sb * cg, sa * sg - ca * sb * cg, cb * cg];
  return { right: x, up: y, forward: [-z[0], -z[1], -z[2]] };
}

/** Compass bearing (0 = north, 90 = east) and elevation above the horizon of a direction. */
export function lookAngles(v: Vec3): { azimuth: number; elevation: number } {
  return {
    azimuth: normalizeDeg(deg(Math.atan2(v[0], v[1]))),
    elevation: deg(Math.asin(Math.max(-1, Math.min(1, v[2])))),
  };
}

/** Unit vector (east, north, up) towards a sky position. */
export function skyVector(azimuthDeg: number, altitudeDeg: number): Vec3 {
  const az = rad(azimuthDeg), alt = rad(altitudeDeg);
  return [Math.sin(az) * Math.cos(alt), Math.cos(az) * Math.cos(alt), Math.sin(alt)];
}

/** Basis for a viewer who looks at (azimuth, elevation) with the horizon level (no roll). */
export function basisFromLook(azimuthDeg: number, elevationDeg: number): Basis {
  const forward = skyVector(azimuthDeg, elevationDeg);
  const right = norm([Math.cos(rad(azimuthDeg)), -Math.sin(rad(azimuthDeg)), 0]);
  const up: Vec3 = [
    right[1] * forward[2] - right[2] * forward[1],
    right[2] * forward[0] - right[0] * forward[2],
    right[0] * forward[1] - right[1] * forward[0],
  ];
  return { forward, right, up: norm(up) };
}

export type Projected = {
  x: number;
  y: number;
  /** true when the point is in front of the camera */
  inFront: boolean;
  /** angle in degrees between the view axis and the target */
  offAxisDeg: number;
};

/**
 * Pinhole projection of a sky position onto a screen of `width` x `height` pixels whose
 * vertical field of view is `fovVDeg`.
 */
export function project(
  azimuthDeg: number,
  altitudeDeg: number,
  basis: Basis,
  width: number,
  height: number,
  fovVDeg: number,
): Projected {
  const s = skyVector(azimuthDeg, altitudeDeg);
  const zc = dot(s, basis.forward);
  const xc = dot(s, basis.right);
  const yc = dot(s, basis.up);
  const focal = height / 2 / Math.tan(rad(fovVDeg) / 2);
  const offAxisDeg = deg(Math.acos(Math.max(-1, Math.min(1, zc))));
  if (zc <= 1e-6) return { x: NaN, y: NaN, inFront: false, offAxisDeg };
  return {
    x: width / 2 + (focal * xc) / zc,
    y: height / 2 - (focal * yc) / zc,
    inFront: true,
    offAxisDeg,
  };
}

/** Exponential smoothing of two bases (component-wise, then re-normalised). */
export function blendBasis(prev: Basis | null, next: Basis, k: number): Basis {
  if (!prev) return next;
  const mix = (a: Vec3, b: Vec3): Vec3 =>
    norm([a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]);
  return {
    forward: mix(prev.forward, next.forward),
    right: mix(prev.right, next.right),
    up: mix(prev.up, next.up),
  };
}

/** Signed shortest turn in degrees (positive = turn right) from heading `from` to `to`. */
export function turnToward(fromDeg: number, toDeg: number): number {
  return ((toDeg - fromDeg + 540) % 360) - 180;
}
