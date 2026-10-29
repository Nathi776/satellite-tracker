import type { GroupInfo } from "../api";
import type { OverlayId } from "../hooks/useOverlays";
import { groupColor } from "../utils/groups";
import "./layers-panel.css";

type Props = {
  groups: GroupInfo[];
  group: string;
  onGroupChange: (id: string) => void;
  overlays: Record<OverlayId, boolean>;
  onToggleOverlay: (id: OverlayId) => void;
  onReset: () => void;
  nakedEyeOnly: boolean;
  onNakedEyeOnlyChange: (v: boolean) => void;
  hasLocation: boolean;
  aboveCount: number | null;
};

const OVERLAYS: { id: OverlayId; label: string; key: string }[] = [
  { id: "track", label: "Ground track", key: "T" },
  { id: "night", label: "Day / night", key: "D" },
  { id: "range", label: "Your range", key: "O" },
  { id: "footprint", label: "Footprint", key: "F" },
  { id: "labels", label: "Labels", key: "L" },
];

/** The left-hand panel on wide screens: what is drawn on the map, in one place. */
export default function LayersPanel({
  groups,
  group,
  onGroupChange,
  overlays,
  onToggleOverlay,
  onReset,
  nakedEyeOnly,
  onNakedEyeOnlyChange,
  hasLocation,
  aboveCount,
}: Props) {
  const rows = groups.filter(g => g.count > 0 || g.id === "all");

  return (
    <aside className="layers" aria-label="Layers">
      <div className="layers__head">
        <b>Layers</b>
        <button type="button" className="layers__link" onClick={onReset}>
          Reset
        </button>
      </div>

      <div className="layers__group" id="layers-sats">
        Satellites
      </div>
      <div role="radiogroup" aria-labelledby="layers-sats">
        {rows.map(g => (
          <label key={g.id} className="layers__row">
            <input
              type="radio"
              name="layers-group"
              checked={g.id === group}
              onChange={() => onGroupChange(g.id)}
            />
            <span className="layers__dot" style={{ background: groupColor(g.id) }} />
            <span className="layers__label">{g.label}</span>
            <span className="layers__n">{g.count.toLocaleString()}</span>
          </label>
        ))}
      </div>

      <div className="layers__group">Overlays</div>
      {OVERLAYS.map(o => (
        <label key={o.id} className="layers__row">
          <input type="checkbox" checked={overlays[o.id]} onChange={() => onToggleOverlay(o.id)} />
          <span className="layers__label">{o.label}</span>
          <kbd>{o.key}</kbd>
        </label>
      ))}

      <div className="layers__group">Your sky</div>
      <label className="layers__row" title={hasLocation ? undefined : "Use My Location first"}>
        <input
          type="checkbox"
          checked={overlays.sky}
          disabled={!hasLocation}
          onChange={() => onToggleOverlay("sky")}
        />
        <span className="layers__label">Satellites above you</span>
        {aboveCount !== null && <span className="layers__n">{aboveCount}</span>}
      </label>
      <label className="layers__row">
        <input
          type="checkbox"
          checked={nakedEyeOnly}
          disabled={!hasLocation || !overlays.sky}
          onChange={e => onNakedEyeOnlyChange(e.target.checked)}
        />
        <span className="layers__label">Only those visible by eye</span>
      </label>

      <div className="layers__keys">
        <span>
          <kbd>S</kbd> style
        </span>
        <span>
          <kbd>/</kbd> search
        </span>
        <span>
          <kbd>Esc</kbd> clear
        </span>
      </div>
    </aside>
  );
}
