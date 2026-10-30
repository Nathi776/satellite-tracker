import { useEffect, useMemo, useRef, useState } from "react";
import Globe, { type GlobeMethods } from "react-globe.gl";
import { Mesh, MeshBasicMaterial, SphereGeometry } from "three";
import type { SatellitePos } from "../api";
import { groupColor } from "../utils/groups";
import "./globe-view.css";

type LatLon = [number, number];

type Props = {
  sats: SatellitePos[];
  selectedName: string | null;
  onSelect: (name: string | null) => void;
  /** orbit ahead of / behind the selected satellite, as [lat, lon] points */
  track: LatLon[];
  past: LatLon[];
  showTrack: boolean;
  observer: { lat: number; lon: number } | null;
  /** where the camera starts when nothing is selected */
  home?: { lat: number; lng: number; altitude: number };
};

const EARTH_RADIUS_KM = 6371;

// one shared sphere; materials are shared per colour
const DOT = new SphereGeometry(1, 12, 8);
const materials = new Map<string, MeshBasicMaterial>();
const material = (color: string) => {
  let m = materials.get(color);
  if (!m) materials.set(color, (m = new MeshBasicMaterial({ color })));
  return m;
};
const asset = (p: string) => `${import.meta.env.BASE_URL}${p}`;

/** Height above the surface in globe radii. Real heights would put GPS and GEO satellites far
 *  off the screen, so very high orbits are squeezed. */
export const altitudeOf = (altKm: number | undefined) => {
  const a = Math.max(0, (altKm ?? 500) / EARTH_RADIUS_KM);
  return a <= 0.5 ? a : 0.5 + (a - 0.5) * 0.15;
};

/** The same satellites as the flat map, on a rotating Earth. */
export default function GlobeView({
  sats,
  selectedName,
  onSelect,
  track,
  past,
  showTrack,
  observer,
  home = { lat: 5, lng: 20, altitude: 2.4 },
}: Props) {
  const globe = useRef<GlobeMethods | undefined>(undefined);
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const selected = sats.find(s => s.name === selectedName) ?? null;

  // camera: start over Africa (or over you), then turn towards whatever gets selected
  useEffect(() => {
    if (!ready || !globe.current) return;
    const start = observer ? { lat: observer.lat, lng: observer.lon, altitude: 2.4 } : home;
    globe.current.pointOfView(start, 0);
    const controls = globe.current.controls();
    controls.autoRotate = false;
    controls.minDistance = 130;
    controls.maxDistance = 900;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  const selectedLat = selected?.lat;
  const selectedLon = selected?.lon;
  const turnedTo = useRef<string | null>(null);
  useEffect(() => {
    if (!ready || !globe.current) return;
    if (selectedName && selectedLat !== undefined && selectedLon !== undefined && turnedTo.current !== selectedName) {
      turnedTo.current = selectedName;
      globe.current.pointOfView({ lat: selectedLat, lng: selectedLon, altitude: 1.9 }, 900);
    }
    if (!selectedName) turnedTo.current = null;
  }, [ready, selectedName, selectedLat, selectedLon]);

  const alt = altitudeOf(selected?.alt_km);
  const paths = useMemo(() => {
    if (!selected || !showTrack) return [];
    const line = (pts: LatLon[], color: string, dash: number) => ({
      pts: pts.map(([lat, lng]) => [lat, lng, alt] as [number, number, number]),
      color,
      dash,
    });
    return [line(past, "rgba(94,234,212,0.55)", 0.015), line(track, "#2dd4bf", 0)].filter(p => p.pts.length > 1);
  }, [selected, showTrack, track, past, alt]);

  const rings = useMemo(() => {
    const r: { lat: number; lng: number; color: string; max: number }[] = [];
    if (observer) r.push({ lat: observer.lat, lng: observer.lon, color: "59,130,246", max: 6 });
    if (selected) r.push({ lat: selected.lat, lng: selected.lon, color: "255,255,255", max: 4 });
    return r;
  }, [observer, selected]);

  return (
    <div className="globe-view" ref={box}>
      {size.w > 0 && (
        <Globe
          ref={globe}
          width={size.w}
          height={size.h}
          globeImageUrl={asset("globe/earth-day.jpg")}
          backgroundImageUrl={asset("globe/night-sky.png")}
          atmosphereColor="#6ea8ff"
          atmosphereAltitude={0.18}
          onGlobeReady={() => setReady(true)}
          onGlobeClick={() => onSelect(null)}
          customLayerData={sats}
          customThreeObject={(d: object) => {
            const sat = d as SatellitePos;
            const dot = new Mesh(DOT, material(sat.name === selectedName ? "#ffffff" : groupColor(sat.group)));
            dot.scale.setScalar(sat.name === selectedName ? 1.9 : 1.1);
            dot.userData = { name: sat.name };
            return dot;
          }}
          customThreeObjectUpdate={(obj: object, d: object) => {
            const sat = d as SatellitePos;
            const at = globe.current?.getCoords(sat.lat, sat.lon, altitudeOf(sat.alt_km));
            if (at) Object.assign((obj as Mesh).position, at);
            (obj as Mesh).scale.setScalar(sat.name === selectedName ? 1.9 : 1.1);
            (obj as Mesh).material = material(sat.name === selectedName ? "#ffffff" : groupColor(sat.group));
          }}
          customLayerLabel={(d: object) => `<div class="globe-tip">${esc((d as SatellitePos).name)}</div>`}
          onCustomLayerClick={(d: object) => onSelect((d as SatellitePos).name)}
          pathsData={paths}
          pathPoints="pts"
          pathPointLat={(p: object) => (p as number[])[0]}
          pathPointLng={(p: object) => (p as number[])[1]}
          pathPointAlt={(p: object) => (p as number[])[2]}
          pathColor="color"
          pathDashLength={(d: object) => ((d as { dash: number }).dash ? 0.01 : 1)}
          pathDashGap={(d: object) => ((d as { dash: number }).dash ? 0.012 : 0)}
          pathStroke={1.2}
          pathTransitionDuration={0}
          ringsData={rings}
          ringColor={(d: object) => (t: number) => `rgba(${(d as { color: string }).color},${1 - t})`}
          ringMaxRadius="max"
          ringPropagationSpeed={2}
          ringRepeatPeriod={1400}
        />
      )}
    </div>
  );
}

const esc = (s: string) => s.replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
