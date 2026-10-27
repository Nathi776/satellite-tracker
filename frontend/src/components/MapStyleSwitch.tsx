import { MAP_STYLES, type MapStyleId } from "../utils/mapStyles";

type Props = { value: MapStyleId; onChange: (id: MapStyleId) => void };

export default function MapStyleSwitch({ value, onChange }: Props) {
  return (
    <div className="map-style" role="group" aria-label="Map style">
      {MAP_STYLES.map(s => (
        <button
          key={s.id}
          type="button"
          aria-pressed={value === s.id}
          className={value === s.id ? "is-active" : undefined}
          onClick={() => onChange(s.id)}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}
