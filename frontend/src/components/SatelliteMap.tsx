import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import InfoPanel from "./InfoPanel";
import { useObserver } from "../hooks/useObserver";
import { useDebounce } from "../hooks/useDebounce";
import SkyCompass from "./SkyCompass";
import {
  fetchGroundTrack,
  fetchPositions,
  fetchVisibility,
  type SatellitePos,
  type VisibilityResponse,
} from "../api";

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

// Satellites above the observer's horizon get a green dot so they stand out.
const visibleIcon = L.divIcon({
  className: "",
  html: '<div style="width:14px;height:14px;border-radius:50%;background:#22c55e;border:2px solid #fff;box-shadow:0 0 6px #22c55e"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

// Panel shows only the highest satellites; the rest are still on the map.
const MAX_PANEL_SATS = 8;

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

const errorMessage = (e: unknown) => (e instanceof Error ? e.message : String(e));
const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

// -------------------
// Component
// -------------------
export default function SatelliteMap() {
  const [search, setSearch] = useState("");
  // Wait until the user stops typing before hitting the API.
  const debouncedSearch = useDebounce(search.trim(), 350);

  const [satellites, setSatellites] = useState<SatellitePos[]>([]);
  const [trackPoints, setTrackPoints] = useState<number[][]>([]);
  const [selected, setSelected] = useState<SatellitePos | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { location, requestLocation } = useObserver();
  const [visibility, setVisibility] = useState<VisibilityResponse | null>(null);

  // -------------------
  // Load visibility
  // -------------------
  useEffect(() => {
    if (!location) return;

    const controller = new AbortController();
    fetchVisibility(location.lat, location.lon, controller.signal)
      .then(data => {
        setVisibility(data);
        setError(null);
      })
      .catch(e => {
        if (isAbort(e)) return;
        setVisibility(null);
        setError(`Could not load visibility: ${errorMessage(e)}`);
      });

    return () => controller.abort();
  }, [location]);

  // -------------------
  // Load satellite positions
  // -------------------
  useEffect(() => {
    const controller = new AbortController();
    fetchPositions(debouncedSearch, controller.signal)
      .then(data => {
        setSatellites(data);
        setError(null);
      })
      .catch(e => {
        if (isAbort(e)) return;
        setSatellites([]);
        setError(`Could not load satellites: ${errorMessage(e)}`);
      });

    return () => controller.abort();
  }, [debouncedSearch]);

  // -------------------
  // Load ground track
  // -------------------
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

  // The backend already returns lat/lon with each visible satellite, so there is
  // nothing to merge with /positions any more.
  const visibleNow = visibility?.visible_now ?? [];

  // -------------------
  // UI
  // -------------------
  return (
    <div style={{ height: "100vh", width: "100vw", position: "relative" }}>
      {/* HEADER */}
      <div
        style={{
          height: 80,
          background: "#121212",
          color: "white",
          padding: "10px 20px",
          boxSizing: "border-box",
        }}
      >
        <h2 style={{ margin: 0 }}>🛰 Satellite Tracker</h2>

        <div style={{ display: "flex", gap: 10, marginTop: 6, alignItems: "center" }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search satellite (ISS, ZACUBE...)"
            style={{
              padding: 6,
              width: 280,
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
            📍 Use My Location
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

        {/* All satellites */}
        {satellites.map(sat => (
          <Marker
            key={sat.name}
            position={[sat.lat, sat.lon]}
            eventHandlers={{
              click: () => setSelected(sat),
            }}
          >
            <Popup>
              <strong>{sat.name}</strong>
            </Popup>
          </Marker>
        ))}

        {/* Observer */}
        {location && (
          <Marker position={[location.lat, location.lon]}>
            <Popup>You are here</Popup>
          </Marker>
        )}

        {/* Visible satellites: exactly what the backend computed */}
        {visibleNow.map(sat => (
          <Marker
            key={`visible-${sat.name}`}
            position={[sat.lat, sat.lon]}
            icon={visibleIcon}
          >
            <Popup>
              <strong>{sat.name}</strong>
              <br />
              Elevation: {sat.altitude_deg}°
              <br />
              Azimuth: {sat.azimuth_deg}°
              <br />
              Distance: {sat.distance_km} km
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

      {/* Visibility panel (outside the map so it isn't tied to Leaflet's layout) */}
      {visibility && (
        <div
          style={{
            position: "absolute",
            right: 20,
            top: 100,
            width: 280,
            maxHeight: "calc(100vh - 140px)",
            overflowY: "auto",
            background: "#111",
            color: "white",
            padding: 12,
            borderRadius: 10,
            zIndex: 1000,
          }}
        >
          <h3 style={{ marginTop: 0 }}>
            🔭 Above Horizon ({visibleNow.length})
          </h3>

          {visibleNow.length === 0 && <div>No satellites above your horizon</div>}

          {visibleNow.slice(0, MAX_PANEL_SATS).map(sat => (
            <div key={sat.name} style={{ marginBottom: 10 }}>
              <strong>{sat.name}</strong>
              <div style={{ fontSize: 12 }}>
                El: {sat.altitude_deg}° | Dist: {sat.distance_km} km
              </div>
              <SkyCompass azimuth={sat.azimuth_deg} />
            </div>
          ))}

          {visibleNow.length > MAX_PANEL_SATS && (
            <div style={{ fontSize: 12, opacity: 0.7 }}>
              + {visibleNow.length - MAX_PANEL_SATS} more lower in the sky (shown on the map)
            </div>
          )}

          <h4 style={{ marginTop: 14 }}>⏭ Next Passes</h4>
          {visibility.next_passes.length === 0 && (
            <div style={{ fontSize: 12 }}>No passes above 10° in the next 24 h</div>
          )}
          {visibility.next_passes.slice(0, 5).map(p => (
            <div key={`${p.name}-${p.rise_time_utc}`} style={{ fontSize: 12, marginBottom: 6 }}>
              <strong>{p.name}</strong>
              <br />
              {new Date(p.rise_time_utc).toLocaleString([], {
                weekday: "short",
                hour: "2-digit",
                minute: "2-digit",
              })}
              {" · peak "}
              {p.max_elevation_deg}°
            </div>
          ))}
        </div>
      )}

      <InfoPanel satellite={selected} />
    </div>
  );
}
