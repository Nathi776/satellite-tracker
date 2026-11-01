export type MapView = "map" | "globe";

/** Flat map or 3D globe. Floats over the map on wide screens; lives in the Layers sheet on phones. */
export default function ViewSwitch({
  view,
  onChange,
  className = "view-switch",
}: {
  view: MapView;
  onChange: (v: MapView) => void;
  className?: string;
}) {
  return (
    <div className={className} role="group" aria-label="View">
      {(["map", "globe"] as const).map(v => (
        <button key={v} type="button" aria-pressed={view === v} onClick={() => onChange(v)}>
          {v === "map" ? "Map" : "3D globe"}
        </button>
      ))}
    </div>
  );
}
