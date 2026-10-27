type Props = {
  nowMs: number;
  /** the moment being shown when the map is not live */
  travelAtMs: number | null;
  stale: boolean;
};

const fmt = (ms: number) =>
  new Date(ms).toLocaleString("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

/** Live status plus the date and time in UTC (what orbit data is measured in). */
export default function UtcClock({ nowMs, travelAtMs, stale }: Props) {
  const shown = travelAtMs ?? nowMs;
  const [date, time] = fmt(shown).split(", ");
  return (
    <div className="clock" aria-live="off">
      {travelAtMs === null ? (
        <span className="clock__status">
          <span className="live-dot" style={{ ["--live" as string]: stale ? "#ef4444" : "#22c55e" }} />
          {stale ? "Offline" : "Live"}
        </span>
      ) : (
        <span className="clock__status">🕑 Time travel</span>
      )}
      <span className="clock__time">
        <span className="clock__date">{date} </span>
        <strong>{time}</strong> UTC
      </span>
    </div>
  );
}
