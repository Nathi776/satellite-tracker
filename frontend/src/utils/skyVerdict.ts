import type { SatPass, VisibleSat } from "../api";

export type Verdict =
  | { kind: "now"; sat: VisibleSat }
  | { kind: "pass"; pass: SatPass; inProgress: boolean }
  | { kind: "none" };

const mag = (m: number | null) => (m === null ? 99 : m);

/** Plain-words brightness for an estimated magnitude (lower = brighter). */
export function brightnessWord(m: number | null): string {
  if (m === null) return "";
  if (m <= -2) return "very bright";
  if (m <= 0) return "bright";
  if (m <= 2) return "easy to see";
  return "dim, look carefully";
}

/**
 * The one thing worth telling the person first:
 *  1. a satellite they can see by eye right now (the brightest one),
 *  2. else the best naked-eye pass still to come (a pass in progress counts),
 *  3. else nothing.
 * "Best" = brightest estimated magnitude, then highest in the sky, then soonest.
 */
export function pickVerdict(sats: VisibleSat[], passes: SatPass[], nowMs: number): Verdict {
  const visibleNow = sats.filter(s => s.naked_eye);
  if (visibleNow.length > 0) {
    const sat = [...visibleNow].sort(
      (a, b) => mag(a.magnitude) - mag(b.magnitude) || b.altitude_deg - a.altitude_deg,
    )[0];
    return { kind: "now", sat };
  }

  const candidates = passes.filter(
    p => p.visibility === "visible" && new Date(p.set_time_utc).getTime() > nowMs,
  );
  if (candidates.length === 0) return { kind: "none" };

  const pass = [...candidates].sort(
    (a, b) =>
      mag(a.magnitude) - mag(b.magnitude) ||
      b.max_elevation_deg - a.max_elevation_deg ||
      a.rise_time_utc.localeCompare(b.rise_time_utc),
  )[0];
  return { kind: "pass", pass, inProgress: new Date(pass.rise_time_utc).getTime() <= nowMs };
}
