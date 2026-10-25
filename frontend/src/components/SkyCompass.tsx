type Props = {
  azimuth: number;
};

const SIZE = 96;

const label = (pos: React.CSSProperties, text: string) => (
  <span
    style={{
      position: "absolute",
      fontSize: 10,
      lineHeight: 1,
      opacity: 0.8,
      ...pos,
    }}
  >
    {text}
  </span>
);

/** Small compass dial. 0° (north) is straight up and azimuth increases clockwise,
 *  so a satellite at azimuth 90° points to the right (east). */
export default function SkyCompass({ azimuth }: Props) {
  return (
    <div style={{ width: SIZE, margin: "6px auto 0" }}>
      <div
        style={{
          width: SIZE,
          height: SIZE,
          borderRadius: "50%",
          border: "2px solid white",
          position: "relative",
          boxSizing: "border-box",
        }}
      >
        {label({ top: 2, left: "50%", transform: "translateX(-50%)" }, "N")}
        {label({ bottom: 2, left: "50%", transform: "translateX(-50%)" }, "S")}
        {label({ left: 4, top: "50%", transform: "translateY(-50%)" }, "W")}
        {label({ right: 4, top: "50%", transform: "translateY(-50%)" }, "E")}

        {/* Needle: its bottom end sits on the dial's centre, and it rotates about that point. */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: "50%",
            width: 2,
            height: "50%",
            background: "red",
            transformOrigin: "bottom center",
            transform: `translateX(-50%) rotate(${azimuth}deg)`,
          }}
        />
      </div>
      <p style={{ textAlign: "center", margin: "4px 0 0", fontSize: 12 }}>
        Azimuth {azimuth}°
      </p>
    </div>
  );
}
