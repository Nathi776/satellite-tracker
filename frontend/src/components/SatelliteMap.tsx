import { useCallback, useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  CircleMarker,
  Popup,
  Polyline,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import InfoPanel from "./InfoPanel";
import SkyPanel from "./SkyPanel";
import { useObserver } from "../hooks/useObserver";
import { useDebounce } from "../hooks/useDebounce";
import { usePolling } from "../hooks/usePolling";
import { useTicker } from "../hooks/useTicker";
import {
  fetchGroundTrack,
  fetchPositions,
  fetchVisibility,
  type VisibilityStatus,
  type VisibleSat,
} from "../api";
import {
  STATUS_STYLE,
  compassPoint,
  formatMag,
  moveInSky,
  moveOnMap,
} from "../utils/sky";
import "./sky.css";

// -------------------
// Fix marker icons
// -------------------
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Satellites above the observer's horizon, coloured by whether they can be seen.
function dotIcon(status: VisibilityStatus, big: boolean, selected: boolean) {
  const size = big ? 18 : 12;
  const color = STATUS_STYLE[status].color;
  const fill = status === "in_shadow" ? "transparent" : color;
  const ring = selected ? ";outline:2px solid #fff;outline-offset:2px" : "";
  return L.divIcon({
    className: "",
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${fill};border:2px solid ${
      big ? "#fff" : color
    };box-shadow:0 0 ${big ? 10 : 4}px ${color}${ring}"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// How often the API is asked again; in between, satellites are moved along their rates.
const VISIBILITY_REFRESH_MS = 5000;
const POSITIONS_REFRESH_MS = 10000;
const STALE_AFTER_S = 20;

// -------------------
// Helpers
// -------------------
/** Split a ground track where it wraps across the ±180° meridian, so Leaflet
 *  doesn't draw a line straight across the whole map. */
function splitTrack(points: number[][]) {
  if (points.length === 0) return [];

  const segments: number[][][] = [];
  let current: number[][] = [points[0]];

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const curr = points[i];

    if (Math.abs(curr[1] - prev[1]) > 180) {
      segments.push(current);
      current = [];
    }
    current.push(curr);
  }

  if (current.length) segments.push(current);
  return segments;
}

const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

// -------------------
// Component
// -------------------
export default function SatelliteMap() {
  // One tick per second drives all animation.
  const nowMs = useTicker(1000);

  const [search, setSearch] = useState("");
  // Wait until the user stops typing before hitting the API.
  const debouncedSearch = useDebounce(search.trim(), 350);

  const [selectedName, setSelectedName] = useState<string | null>(null); // map marker
  const [selectedSky, setSelectedSky] = useState<string | null>(null); // radar / list
  const [nakedEyeOnly, setNakedEyeOnly] = useState(true);
  const [trackPoints, setTrackPoints] = useState<number[][]>([]);

  const { location, requestLocation } = useObserver();

  // -------------------
  // Live data
  // -------------------
  const positionsFetcher = useCallback(
    (signal: AbortSignal) => fetchPositions(debouncedSearch, signal),
    [debouncedSearch],
  );
  const positions = usePolling(positionsFetcher, POSITIONS_REFRESH_MS);

  const visibilityFetcher = useMemo(
    () =>
      location
        ? (signal: AbortSignal) => fetchVisibility(location.lat, location.lon, 48, signal)
        : null,
    [location],
  );
  const visibility = usePolling(visibilityFetcher, VISIBILITY_REFRESH_MS);

  // Seconds since each data set was computed: time in the browser since it arrived,
  // plus how old the server said it already was.
  const positionsElapsed = positions.receivedAt ? (nowMs - positions.receivedAt) / 1000 : 0;
  const visibilityElapsed = visibility.receivedAt
    ? (nowMs - visibility.receivedAt) / 1000 + (visibility.data?.age_seconds ?? 0)
    : 0;

  const livePositions = useMemo(
    () => (positions.data ?? []).map(s => moveOnMap(s, positionsElapsed)),
    [positions.data, positionsElapsed],
  );

  // Everything above the horizon, moved to this instant. Anything that has set since the
  // last refresh drops out until the next one.
  const liveSats = useMemo(
    () =>
      (visibility.data?.visible_now ?? [])
        .map(s => moveInSky(s, visibilityElapsed))
        .filter((s): s is VisibleSat => s !== null),
    [visibility.data, visibilityElapsed],
  );

  const mapSats = nakedEyeOnly ? liveSats.filter(s => s.naked_eye) : liveSats;

  const selectedPos = livePositions.find(s => s.name === selectedName) ?? null;

  const visibilityAge = visibility.receivedAt
    ? Math.round((nowMs - visibility.receivedAt) / 1000)
    : null;
  const stale =
    visibility.error !== null || (visibilityAge !== null && visibilityAge > STALE_AFTER_S);

  const error = visibility.error ?? positions.error;

  // -------------------
  // Ground track (only while searching)
  // -------------------
  // A real effect (not useMemo) so the cleanup runs: a slow response for an old search
  // is cancelled instead of overwriting the track for the current one.
  useEffect(() => {
    if (!debouncedSearch) {
      setTrackPoints([]);
      return;
    }
    const controller = new AbortController();
    fetchGroundTrack(debouncedSearch, controller.signal)
      .then(data => setTrackPoints(data.track.map(p => [p.lat, p.lon])))
      .catch(e => {
        if (!isAbort(e)) setTrackPoints([]); // e.g. 404 for a search with no single match
      });
    return () => controller.abort();
  }, [debouncedSearch]);

  // -------------------
  // UI
  // -------------------
  return (
    <div style={{ height: "100vh", width: "100vw", position: "relative" }}>
      {/* HEADER */}
      <div
        style={{
          minHeight: 80,
          background: "#121212",
          color: "white",
          padding: "10px 20px",
          boxSizing: "border-box",
        }}
      >
        <h2 style={{ margin: 0 }}>🛰 Satellite Tracker</h2>

        <div
          style={{
            display: "flex",
            gap: 10,
            marginTop: 6,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search satellite (ISS, ZACUBE...)"
            style={{
              padding: 6,
              width: 280,
              maxWidth: "100%",
              borderRadius: 6,
              border: "none",
            }}
          />

          <button
            onClick={requestLocation}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              background: "#0077ff",
              color: "white",
              border: "none",
              cursor: "pointer",
            }}
          >
            📍 {location ? "Update My Location" : "Use My Location"}
          </button>

          {error && (
            <span style={{ color: "#ff8a8a", fontSize: 13 }} role="alert">
              ⚠ {error}
            </span>
          )}
        </div>
      </div>

      {/* MAP */}
      <MapContainer
        center={[0, 0]}
        zoom={2}
        style={{ height: "calc(100vh - 80px)" }}
      >
        <TileLayer
          attribution="© OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* All satellites (small dots, moving live) */}
        {livePositions.map(sat => (
          <CircleMarker
            key={sat.name}
            center={[sat.lat, sat.lon]}
            radius={sat.name === selectedName ? 7 : 4}
            pathOptions={{
              color: "#1d4ed8",
              fillColor: "#3b82f6",
              fillOpacity: 0.85,
              weight: sat.name === selectedName ? 3 : 1,
            }}
            eventHandlers={{
              click: () => setSelectedName(sat.name),
            }}
          >
            <Popup>
              <strong>{sat.name}</strong>
            </Popup>
          </CircleMarker>
        ))}

        {/* Observer */}
        {location && (
          <Marker position={[location.lat, location.lon]}>
            <Popup>You are here</Popup>
          </Marker>
        )}

        {/* Satellites above your horizon, coloured by visibility */}
        {mapSats.map(sat => (
          <Marker
            key={`sky-${sat.name}`}
            position={[sat.lat, sat.lon]}
            icon={dotIcon(sat.status, sat.naked_eye, sat.name === selectedSky)}
            zIndexOffset={sat.naked_eye ? 1000 : 0}
            eventHandlers={{
              click: () => setSelectedSky(sat.name),
            }}
          >
            <Popup>
              <strong>{sat.name}</strong>
              <br />
              {STATUS_STYLE[sat.status].label}
              <br />
              Elevation: {sat.altitude_deg.toFixed(0)}° · {compassPoint(sat.azimuth_deg)} (
              {sat.azimuth_deg.toFixed(0)}°)
              <br />
              Distance: {Math.round(sat.distance_km).toLocaleString()} km
              {sat.magnitude !== null && (
                <>
                  <br />
                  Est. magnitude: {formatMag(sat.magnitude)}
                </>
              )}
            </Popup>
          </Marker>
        ))}

        {/* Ground track */}
        {splitTrack(trackPoints).map((seg, i) => (
          <Polyline
            key={i}
            positions={seg as [number, number][]}
            pathOptions={{
              color: "#00ffcc",
              weight: 2,
              dashArray: "5,5",
            }}
          />
        ))}
      </MapContainer>

      {/* Your sky: outside the map so it isn't tied to Leaflet's layout */}
      {visibility.data ? (
        <SkyPanel
          visibility={visibility.data}
          sats={liveSats}
          nakedEyeOnly={nakedEyeOnly}
          onNakedEyeOnlyChange={setNakedEyeOnly}
          nowMs={nowMs}
          ageSeconds={visibilityAge}
          stale={stale}
          selected={selectedSky}
          onSelect={setSelectedSky}
        />
      ) : (
        <div className="sky-hint">
          {location ? (
            visibility.error ? (
              <>⚠ Couldn’t load your sky: {visibility.error}</>
            ) : (
              <>Working out what’s above you…</>
            )
          ) : (
            <>
              📍 Tap <strong>Use My Location</strong> to see which satellites are above you, whether
              you can see them, and when the next pass is.
            </>
          )}
        </div>
      )}

      <InfoPanel satellite={selectedPos} />
    </div>
  );
}
