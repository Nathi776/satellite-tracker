import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import L from "leaflet";
import { useEffect, useState, useRef } from "react";
import "leaflet/dist/leaflet.css";

const icon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34]
});

type Satellite = {
  name: string;
  lat: number;
  lon: number;
  alt_km: number;
  country?: string;
};

export default function SatelliteMap() {
  const [sats, setSats] = useState<Satellite[]>([]);
  const [track, setTrack] = useState<[number, number][]>([]);
  const mapRef = useRef<L.Map>(null);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/positions")
      .then(res => res.json())
      .then(data => {
        console.log("SAT DATA:", data); // 👈 DEBUG
        setSats(data);
      })
      .catch(err => console.error("Error fetching satellites:", err));
  }, []);

  useEffect(() => {
    if (mapRef.current) {
      setTimeout(() => {
        mapRef.current?.invalidateSize();
      }, 500);
    }
  }, []);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/groundtrack/ZACube-1")
      .then(res => res.json())
      .then(data => {
        const points = data.track.map((p: any) => [p.lat, p.lon]);
        setTrack(points);
      });
  }, []);

  return (
    <div style={{ height: "100vh", width: "100%" }}>
      <MapContainer
        ref={mapRef}
        center={[0, 20]}
        zoom={2}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution="© OpenStreetMap"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {sats.map((sat, i) => (
          <Marker
            key={i}
            position={[sat.lat, sat.lon]}
            icon={icon}
          >
            <Popup>
              <b>{sat.name}</b><br />
              {sat.country && <>Country: {sat.country}<br /></>}
              Altitude: {sat.alt_km.toFixed(1)} km
            </Popup>
          </Marker>
        ))}

        {track.length > 0 && (
          <Polyline
            positions={track}
            pathOptions={{ color: "red", weight: 3 }}
          />
        )}

      </MapContainer>
    </div>
  );
}
