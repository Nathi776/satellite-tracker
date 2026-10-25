import type { VisibleSat } from "../api";
import { STATUS_STYLE } from "../utils/sky";

type Props = {
  sats: VisibleSat[];
  selected: string | null;
  onSelect: (name: string | null) => void;
  /** shown in the middle of the dial when there is nothing to plot */
  emptyMessage?: string;
};

const VIEW = 300;
const C = VIEW / 2;
const R = 122; // radius of the horizon circle

/**
 * Sky radar: the dome above you flattened onto a disc.
 *   - the centre is straight overhead (elevation 90 deg), the rim is the horizon
 *   - north is at the top and east on the LEFT, as on a star chart: the map is what you
 *     see when you look up, not what you'd see looking down at the ground
 */
function project(azimuthDeg: number, elevationDeg: number) {
  const r = (R * (90 - elevationDeg)) / 90;
  const az = (azimuthDeg * Math.PI) / 180;
  return { x: C - r * Math.sin(az), y: C - r * Math.cos(az) };
}

export default function SkyRadar({ sats, selected, onSelect, emptyMessage }: Props) {
  // draw the interesting ones last so they sit on top of the crowd
  const ordered = [...sats].sort(
    (a, b) => Number(a.naked_eye) - Number(b.naked_eye) || Number(a.name === selected) - Number(b.name === selected),
  );
  const nakedEye = sats.filter(s => s.naked_eye).length;

  return (
    <svg
      viewBox={`0 0 ${VIEW} ${VIEW}`}
      role="group"
      aria-label={`Sky radar: ${sats.length} satellites above the horizon, ${nakedEye} visible to the naked eye`}
      style={{ width: "100%", maxWidth: 300, display: "block", margin: "0 auto", touchAction: "manipulation" }}
      onClick={() => onSelect(null)}
    >
      <defs>
        <radialGradient id="sky-bg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#14213d" />
          <stop offset="100%" stopColor="#0a1124" />
        </radialGradient>
      </defs>

      {/* dome */}
      <circle cx={C} cy={C} r={R} fill="url(#sky-bg)" stroke="#5b6b8f" strokeWidth={1.5} />
      {[30, 60].map(el => (
        <g key={el}>
          <circle cx={C} cy={C} r={(R * (90 - el)) / 90} fill="none" stroke="#2c3a5c" strokeDasharray="3 4" />
          <text
            x={C + 3}
            y={C - (R * (90 - el)) / 90 + 11}
            fontSize={9}
            fill="#6f7fa5"
          >
            {el}°
          </text>
        </g>
      ))}
      <line x1={C} y1={C - R} x2={C} y2={C + R} stroke="#2c3a5c" />
      <line x1={C - R} y1={C} x2={C + R} y2={C} stroke="#2c3a5c" />
      <circle cx={C} cy={C} r={2} fill="#6f7fa5" />

      {/* cardinal directions (east on the left: see project()) */}
      {[
        ["N", C, C - R - 7],
        ["S", C, C + R + 14],
        ["E", C - R - 12, C + 4],
        ["W", C + R + 12, C + 4],
      ].map(([label, x, y]) => (
        <text
          key={label as string}
          x={x as number}
          y={y as number}
          fontSize={12}
          fontWeight={700}
          textAnchor="middle"
          fill={label === "N" ? "#ff6b6b" : "#c8d1e8"}
        >
          {label}
        </text>
      ))}

      {/* satellites */}
      {ordered.map(sat => {
        const { x, y } = project(sat.azimuth_deg, sat.altitude_deg);
        const style = STATUS_STYLE[sat.status];
        const isSelected = sat.name === selected;
        const hollow = sat.status === "in_shadow";
        const radius = sat.naked_eye ? 5.5 : 3.2;

        return (
          <g
            key={sat.name}
            transform={`translate(${x.toFixed(1)} ${y.toFixed(1)})`}
            style={{ cursor: "pointer" }}
            role={sat.naked_eye ? "button" : undefined}
            tabIndex={sat.naked_eye ? 0 : undefined}
            aria-label={sat.naked_eye ? `${sat.name}, ${Math.round(sat.altitude_deg)}° up` : undefined}
            onClick={e => {
              e.stopPropagation();
              onSelect(isSelected ? null : sat.name);
            }}
            onKeyDown={e => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(isSelected ? null : sat.name);
              }
            }}
          >
            <title>
              {sat.name} · {Math.round(sat.altitude_deg)}° up · {STATUS_STYLE[sat.status].label}
            </title>
            <circle r={10} fill="transparent" /* bigger touch target */ />
            {sat.naked_eye && <circle r={10} fill={style.color} opacity={0.22} />}
            {isSelected && <circle r={radius + 5} fill="none" stroke="#fff" strokeWidth={1.5} />}
            <circle
              r={radius}
              fill={hollow ? "none" : style.color}
              stroke={hollow ? style.color : sat.naked_eye ? "#fff" : "none"}
              strokeWidth={hollow ? 1.2 : 1}
              opacity={sat.naked_eye || isSelected ? 1 : 0.85}
            />
            {(sat.naked_eye || isSelected) && (
              <text
                x={radius + 4}
                y={3.5}
                fontSize={10}
                fill="#fff"
                stroke="#0a1124"
                strokeWidth={3}
                paintOrder="stroke"
              >
                {sat.name.length > 16 ? `${sat.name.slice(0, 15)}…` : sat.name}
              </text>
            )}
          </g>
        );
      })}

      {sats.length === 0 && emptyMessage && (
        <text x={C} y={C + 4} fontSize={11} textAnchor="middle" fill="#8b93a7">
          {emptyMessage}
        </text>
      )}
    </svg>
  );
}
