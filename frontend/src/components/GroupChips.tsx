import type { GroupInfo } from "../api";
import { compactCount, groupColor } from "../utils/groups";
import "./map-ui.css";

type Props = {
  groups: GroupInfo[];
  active: string;
  onChange: (id: string) => void;
};

/** Filter chips: one per satellite group, coloured like its dots on the map. */
export default function GroupChips({ groups, active, onChange }: Props) {
  if (groups.length === 0) return null;

  return (
    <div className="chips" role="group" aria-label="Filter satellites by group">
      {groups
        .filter(g => g.count > 0 || g.id === "all")
        .map(g => (
          <button
            key={g.id}
            type="button"
            className="chip"
            aria-pressed={g.id === active}
            onClick={() => onChange(g.id)}
            title={`${g.count.toLocaleString()} satellites`}
            style={{ ["--chip" as string]: groupColor(g.id) }}
          >
            <span className="chip__dot" />
            {g.label}
            <small>{compactCount(g.count)}</small>
          </button>
        ))}
    </div>
  );
}
