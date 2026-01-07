export default function InfoPanel({ satellite }: any) {
  if (!satellite) return null;

  return (
    <div style={{
      position: "absolute",
      bottom: 20,
      left: 350,
      background: "#000c",
      color: "white",
      padding: 12,
      borderRadius: 10,
      minWidth: 220
    }}>
      <h3>{satellite.name}</h3>
      <div>Latitude: {satellite.lat.toFixed(2)}</div>
      <div>Longitude: {satellite.lon.toFixed(2)}</div>
      <div>Altitude: {satellite.alt_km?.toFixed(1)} km</div>

      {satellite.speed_kms && (
        <div>Speed: {satellite.speed_kms.toFixed(2)} km/s</div>
      )}

      {satellite.period_min && (
        <div>Orbit: {satellite.period_min.toFixed(1)} min</div>
      )}
    </div>
  );
}
