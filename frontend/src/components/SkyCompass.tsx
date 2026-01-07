type Props = {
  azimuth: number;
};

export default function SkyCompass({ azimuth }: Props) {
  return (
    <div style={{
      width: 120,
      height: 120,
      borderRadius: "50%",
      border: "3px solid white",
      position: "relative",
      margin: "auto"
    }}>
      <div style={{
        position: "absolute",
        top: "50%",
        left: "50%",
        width: "2px",
        height: "50%",
        background: "red",
        transform: `rotate(${azimuth}deg) translateY(-50%)`,
        transformOrigin: "bottom center"
      }} />
      <p style={{ textAlign: "center", marginTop: 130 }}>Azimuth {azimuth}°</p>
    </div>
  );
}
