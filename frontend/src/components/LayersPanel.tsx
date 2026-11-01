import type { GroupInfo } from "../api";
import type { OverlayId } from "../hooks/useOverlays";
import { groupColor } from "../utils/groups";
import { MAP_STYLES, type MapStyleId } from "../utils/mapStyles";
import PushAlerts from "./PushAlerts";
import ViewSwitch, { type MapView } from "./ViewSwitch";
import "./layers-panel.css";

type Props = {
  groups: GroupInfo[];
  /** ids of the groups being shown; empty = all */
  selected: string[];
  onToggleGroup: (id: string) => void;
  onShowAllGroups: () => void;
  overlays: Record<OverlayId, boolean>;
  onToggleOverlay: (id: OverlayId) => void;
  onReset: () => void;
  nakedEyeOnly: boolean;
  onNakedEyeOnlyChange: (v: boolean) => void;
  hasLocation: boolean;
  location?: { lat: number; lon: number } | null;
  aboveCount: number | null;
  /** "sheet" is the phone version: map style and limit inside, no shortcut hints */
  variant?: "panel" | "sheet";
  mapStyleId?: MapStyleId;
  view?: MapView;
  onViewChange?: (v: MapView) => void;
  onMapStyleChange?: (id: MapStyleId) => void;
  limit?: number;
  limits?: number[];
  onLimitChange?: (n: number) => void;
  onClose?: () => void;
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
  selected,
  onToggleGroup,
  onShowAllGroups,
  overlays,
  onToggleOverlay,
  onReset,
  nakedEyeOnly,
  onNakedEyeOnlyChange,
  hasLocation,
  location = null,
  aboveCount,
  variant = "panel",
  mapStyleId,
  onMapStyleChange,
  view,
  onViewChange,
  limit,
  limits,
  onLimitChange,
  onClose,
}: Props) {
  const sheet = variant === "sheet";
  const rows = groups.filter(g => g.count > 0 || g.id === "all");

  return (
    <aside className={`layers${sheet ? " layers--sheet" : ""}`} aria-label="Layers">
      <div className="layers__head">
        <b>Layers</b>
        <span>
          <button type="button" className="layers__link" onClick={onReset}>
            Reset
          </button>
          {onClose && (
            <button type="button" className="layers__link" onClick={onClose}>
              Done
            </button>
          )}
        </span>
      </div>

      {sheet && view && onViewChange && (
        <ViewSwitch view={view} onChange={onViewChange} className="layers__seg layers__seg--view" />
      )}

      {sheet && mapStyleId && onMapStyleChange && view !== "globe" && (
        <div className="layers__seg" role="group" aria-label="Map style">
          {MAP_STYLES.map(m => (
            <button
              key={m.id}
              type="button"
              aria-pressed={mapStyleId === m.id}
              onClick={() => onMapStyleChange(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
      )}

      <div className="layers__group" id="layers-sats">
        Satellites
      </div>
      <div role="group" aria-labelledby="layers-sats">
        {rows.map(g => {
          const isAll = g.id === "all";
          return (
            <label key={g.id} className="layers__row">
              <input
                type="checkbox"
                checked={isAll ? selected.length === 0 : selected.includes(g.id)}
                onChange={() => (isAll ? onShowAllGroups() : onToggleGroup(g.id))}
              />
              <span className="layers__dot" style={{ background: groupColor(g.id) }} />
              <span className="layers__label">{g.label}</span>
              <span className="layers__n">{g.count.toLocaleString()}</span>
            </label>
          );
        })}
      </div>

      <div className="layers__group">Overlays</div>
      {OVERLAYS.filter(o => !(sheet && o.id === "labels")).map(o => (
        <label key={o.id} className="layers__row">
          <input type="checkbox" checked={overlays[o.id]} onChange={() => onToggleOverlay(o.id)} />
          <span className="layers__label">{o.label}</span>
          {!sheet && <kbd>{o.key}</kbd>}
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

      <div className="layers__group">Alerts</div>
      <PushAlerts location={location} />

      {sheet && limit !== undefined && limits && onLimitChange && (
        <label className="layers__row layers__limit">
          <span className="layers__label">Show up to</span>
          <select value={limit} onChange={e => onLimitChange(Number(e.target.value))}>
            {limits.map(n => (
              <option key={n} value={n}>
                {n.toLocaleString()}
              </option>
            ))}
          </select>
        </label>
      )}

      {!sheet && (
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
      )}
    </aside>
  );
}
