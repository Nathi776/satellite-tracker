import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import InfoPanel from "./InfoPanel";
import { useObserver } from "../hooks/useObserver";
import SkyCompass from "./SkyCompass";

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

// -------------------
// Helpers
// -------------------
function splitTrack(points: number[][]) {
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

// -------------------
// Types
// -------------------
type SatellitePos = {
  name: string;
  lat: number;
  lon: number;
  alt?: number;
};

type VisibleSat = {
  name: string;
  altitude_deg: number;
  azimuth_deg: number;
  distance_km: number;
};

type VisibilityResponse = {
  visible_now: VisibleSat[];
  next_passes: {
    name: string;
    rise_time_utc: string;
  }[];
};

// -------------------
// Component
// -------------------
export default function SatelliteMap() {
  const [search, setSearch] = useState("");
  const [satellites, setSatellites] = useState<SatellitePos[]>([]);
  const [tracks, setTracks] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);

  const { location, requestLocation } = useObserver();
  const [visibility, setVisibility] = useState<VisibilityResponse | null>(null);

  // -------------------
  // Load visibility
  // -------------------
  useEffect(() => {
    if (!location) return;

    fetch(
      `http://127.0.0.1:8000/observer/visibility?lat=${location.lat}&lon=${location.lon}`
    )
      .then(res => res.json())
      .then(data => setVisibility(data))
      .catch(() => setVisibility(null));
  }, [location]);

  // -------------------
  // Load satellite positions
  // -------------------
  useEffect(() => {
    fetch(`http://127.0.0.1:8000/positions?search=${search}`)
      .then(res => res.json())
      .then(data => setSatellites(data))
      .catch(() => setSatellites([]));
  }, [search]);

  // -------------------
  // Load ground track
  // -------------------
  useEffect(() => {
    if (!search.trim()) {
      setTracks([]);
      return;
    }

    fetch(`http://127.0.0.1:8000/groundtrack/${encodeURIComponent(search)}`)
      .then(res => res.json())
      .then(data => {
        if (data.track) {
          setTracks([
            {
              name: search,
              points: data.track.map((p: any) => [p.lat, p.lon]),
            },
          ]);
        }
      })
      .catch(() => setTracks([]));
  }, [search]);

  // -------------------
  // Merge visibility + positions
  // -------------------
  const visibleMarkers =
    visibility?.visible_now
      .map(vs => {
        const pos = satellites.find(s => s.name === vs.name);
        if (!pos) return null;

        return {
          ...vs,
          lat: pos.lat,
          lon: pos.lon,
        };
      })
      .filter(Boolean) || [];

  // -------------------
  // UI
  // -------------------
  return (
    <div style={{ height: "100vh", width: "100vw" }}>
      {/* HEADER */}
      <div
        style={{
          height: 80,
          background: "#121212",
          color: "white",
          padding: "10px 20px",
        }}
      >
        <h2 style={{ margin: 0 }}>🛰 Satellite Tracker</h2>

        <div style={{ display: "flex", gap: 10, marginTop: 6 }}>
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

        {/* Visible satellites */}
        {visibleMarkers.map((sat: any) => (
          <Marker key={sat.name} position={[sat.lat, sat.lon]}>
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

        {/* Visibility Panel */}
        {visibility && (
          <div
            style={{
              position: "absolute",
              right: 20,
              top: 100,
              width: 280,
              background: "#111",
              color: "white",
              padding: 12,
              borderRadius: 10,
              zIndex: 1000,
            }}
          >
            <h3>🔭 Visible Now</h3>

            {visibility.visible_now.length === 0 && (
              <div>No satellites visible</div>
            )}

            {visibility.visible_now.map(sat => (
              <div key={sat.name} style={{ marginBottom: 10 }}>
                <strong>{sat.name}</strong>
                <div style={{ fontSize: 12 }}>
                  El: {sat.altitude_deg}° | Dist: {sat.distance_km} km
                </div>
                <SkyCompass azimuth={sat.azimuth_deg} />
              </div>
            ))}

            <h4 style={{ marginTop: 10 }}>⏭ Next Passes</h4>
            {visibility.next_passes.slice(0, 5).map(p => (
              <div key={p.name} style={{ fontSize: 12 }}>
                {p.name}
                <br />
                {new Date(p.rise_time_utc).toLocaleTimeString()}
              </div>
            ))}
          </div>
        )}

        {/* Ground tracks */}
        {tracks.map(track =>
          splitTrack(track.points).map((seg, i) => (
            <Polyline
              key={i}
              positions={seg}
              pathOptions={{
                color: "#00ffcc",
                weight: 2,
                dashArray: "5,5",
              }}
            />
          ))
        )}
      </MapContainer>

      <InfoPanel satellite={selected} />
    </div>
  );
}
