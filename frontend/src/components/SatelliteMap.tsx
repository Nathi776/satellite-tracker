import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import { useEffect, useState } from "react";
import "leaflet/dist/leaflet.css";

const icon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41]
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

  useEffect(() => {
    const fetchData = () => {
      fetch("http://127.0.0.1:8000/positions")
        .then(res => res.json())
        .then(data => setSats(data));
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <MapContainer
      center={[-5, 20]}
      zoom={3}
      style={{ height: "100vh", width: "100%" }}
    >
      <TileLayer
        attribution="© OpenStreetMap"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {sats.map((sat, i) => (
        <Marker key={i} position={[sat.lat, sat.lon]} icon={icon}>
          <Popup>
            <b>{sat.name}</b><br />
            {sat.country && <>Country: {sat.country}<br /></>}
            Altitude: {sat.alt_km.toFixed(1)} km
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
