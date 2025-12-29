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

// Fix marker icon issue
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

type Satellite = {
  name: string;
  lat: number;
  lon: number;
  alt_km: number;
};

type GroundTrack = {
  name: string;
  points: [number, number][];
};

function App() {
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [tracks, setTracks] = useState<GroundTrack[]>([]);
  const [positions, setPositions] = useState<Record<string, number>>({});

  // Load live satellite positions
  useEffect(() => {
    fetch("http://127.0.0.1:8000/positions")
      .then((res) => res.json())
      .then((data) => setSatellites(data))
      .catch(console.error);
  }, []);

  // Load ground tracks
  useEffect(() => {
    async function loadTracks() {
      try {
        const res = await fetch("http://127.0.0.1:8000/positions");
        const sats = await res.json();

        const trackPromises = sats.map(async (sat: any) => {
          const res = await fetch(
            `http://127.0.0.1:8000/groundtrack/${sat.name}`
          );
          const data = await res.json();

          if (!data || !data.track) {
            return { name: sat.name, points: [] };
          }

          return {
            name: sat.name,
            points: data.track.map((p: any) => [p.lat, p.lon]),
          };
        });

        const allTracks = (await Promise.all(trackPromises)).filter(
          (t) => t.points && t.points.length > 0
        );

        setTracks(allTracks);
      } catch (err) {
        console.error("Failed to load tracks:", err);
      }
    }

    loadTracks();
  }, []);

  // Animate satellites
  useEffect(() => {
    const interval = setInterval(() => {
      setPositions((prev) => {
        const updated = { ...prev };

        tracks.forEach((track) => {
          const max = track.points.length;
          updated[track.name] =
            (prev[track.name] + 1) % max;
        });

        return updated;
      });
    }, 500); // speed (lower = faster)

    return () => clearInterval(interval);
  }, [tracks]);

  return (
    <MapContainer
      center={[0, 20]}
      zoom={2}
      style={{ height: "100vh", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Satellite Markers */}
      {satellites.map((sat) => (
        <Marker key={sat.name} position={[sat.lat, sat.lon]}>
          <Popup>
            <strong>{sat.name}</strong>
            <br />
            Altitude: {sat.alt_km.toFixed(2)} km
          </Popup>
        </Marker>
      ))}

      {/* Ground Tracks */}
      {tracks.map((track, idx) => (
        <Polyline
          key={track.name}
          positions={track.points}
          pathOptions={{
            color: ["red", "blue", "green", "orange", "purple"][idx % 5],
            weight: 2,
            opacity: 0.8,
          }}
        />
      ))}
    </MapContainer>
  );
}

export default App;
