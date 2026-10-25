/** One colour per satellite group, used on the map dots and on the filter chips. */
export const GROUP_COLORS: Record<string, string> = {
  all: "#e8ecf4",
  stations: "#ef4444",
  africa: "#d946ef",
  weather: "#06b6d4",
  navigation: "#84cc16",
  starlink: "#64748b",
  oneweb: "#6366f1",
  comms: "#f97316",
  other: "#94a3b8",
};

export const groupColor = (id: string | undefined) => GROUP_COLORS[id ?? "other"] ?? GROUP_COLORS.other;

/** 8432 -> "8.4k", 312 -> "312" */
export const compactCount = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n));
