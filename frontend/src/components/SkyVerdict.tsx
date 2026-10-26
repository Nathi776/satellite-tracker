import type { SatPass, VisibleSat } from "../api";
import { brightnessWord, pickVerdict } from "../utils/skyVerdict";
import { compassPoint, formatClock, formatDay, formatMag, relativeTime } from "../utils/sky";
import { RemindButton } from "./PassCard";

type Props = {
  sats: VisibleSat[];
  passes: SatPass[];
  nowMs: number;
  darkEnough: boolean;
  onSelect: (name: string) => void;
};

/** The headline of the panel: what to look at now, or when to look next. */
export default function SkyVerdict({ sats, passes, nowMs, darkEnough, onSelect }: Props) {
  const verdict = pickVerdict(sats, passes, nowMs);

  if (verdict.kind === "now") {
    const { sat } = verdict;
    const word = brightnessWord(sat.magnitude);
    return (
      <div className="sky-verdict sky-verdict--now">
        <small className="sky-verdict__label">👀 Look up now</small>
        <strong>{sat.name}</strong>
        <div>
          {Math.round(sat.altitude_deg)}° up, towards {compassPoint(sat.azimuth_deg)}
          {word && <> · {word}</>}
          {sat.magnitude !== null && <small> (mag {formatMag(sat.magnitude)})</small>}
        </div>
        <button type="button" className="sky-remind" onClick={() => onSelect(sat.name)}>
          Show on radar
        </button>
      </div>
    );
  }

  if (verdict.kind === "pass") {
    const { pass, inProgress } = verdict;
    const word = brightnessWord(pass.magnitude);
    return (
      <div className="sky-verdict">
        <small className="sky-verdict__label">
          {inProgress ? "👀 Happening now" : "⭐ Best pass coming up"}
        </small>
        <strong>{pass.name}</strong>
        <div>
          {formatDay(pass.rise_time_utc)} · {formatClock(pass.rise_time_utc)}{" "}
          <small>({inProgress ? "in progress" : relativeTime(pass.rise_time_utc, nowMs)})</small>
        </div>
        <small>
          {pass.rise_direction} → {pass.set_direction} · peaks at {Math.round(pass.max_elevation_deg)}°
          {word && <> · {word}</>}
        </small>
        <RemindButton pass={pass} nowMs={nowMs} />
      </div>
    );
  }

  return (
    <div className="sky-verdict sky-verdict--none">
      <small className="sky-verdict__label">Nothing to see by eye</small>
      <div>
        {darkEnough
          ? "No bright satellite is overhead or due in the next 48 hours."
          : "It is too bright now, and no bright pass is due in the next 48 hours."}
      </div>
      <small>Untick “Naked-eye only” to see fainter satellites.</small>
    </div>
  );
}
