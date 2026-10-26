import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { VisibleSat } from "../api";
import { useDeviceOrientation } from "../hooks/useDeviceOrientation";
import {
  basisFromLook,
  lookAngles,
  normalizeDeg,
  project,
  turnToward,
  type Basis,
} from "../utils/orientation";
import { STATUS_STYLE, compassPoint, formatMag } from "../utils/sky";
import "./sky-view.css";

type Props = {
  sats: VisibleSat[];
  selected: string | null;
  onSelect: (name: string | null) => void;
  onClose: () => void;
  /** magnetic declination at the observer (east positive), to turn compass bearings into true ones */
  declinationDeg?: number;
};

/** Vertical field of view of a typical rear phone camera held upright, in degrees. */
const FOV_V = 65;
const TAP_RADIUS = 30;
const POINTS: [number, string][] = [
  [0, "N"], [45, "NE"], [90, "E"], [135, "SE"], [180, "S"], [225, "SW"], [270, "W"], [315, "NW"],
];

type Placed = { sat: VisibleSat; x: number; y: number };

/**
 * Full-screen "sky view": hold the phone up and satellites appear where they really are.
 * The phone's compass and tilt aim a virtual camera; optionally the rear camera is shown
 * behind it. Without sensors (a computer) you drag to look around instead.
 */
export default function SkyView({ sats, selected, onSelect, onClose, declinationDeg = 0 }: Props) {
  const [headingFix, setHeadingFix] = useState(0);
  const { status, compassKnown, basis: sensorBasis, start } = useDeviceOrientation(headingFix, declinationDeg);
  const [started, setStarted] = useState(false);
  const [wantCamera, setWantCamera] = useState(true);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [hud, setHud] = useState({ az: 0, el: 0 });

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const satsRef = useRef(sats);
  const selectedRef = useRef(selected);
  const placed = useRef<Placed[]>([]);
  const manual = useRef({ az: 180, el: 35 }); // drag-to-look fallback
  const sensorSeen = useRef(false);
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);

  useEffect(() => {
    satsRef.current = sats;
    selectedRef.current = selected;
  }, [sats, selected]);

  const begin = useCallback(async () => {
    setStarted(true);
    await start();
    if (wantCamera && navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
          audio: false,
        });
        const video = videoRef.current;
        if (video) {
          video.srcObject = stream;
          await video.play().catch(() => undefined);
          setCameraOn(true);
        } else {
          stream.getTracks().forEach(t => t.stop());
        }
      } catch {
        setCameraError("Camera not available: showing the plain sky instead.");
      }
    } else if (wantCamera) {
      setCameraError("Camera needs a secure (https) page: showing the plain sky instead.");
    }
  }, [start, wantCamera]);

  // Stop the camera when leaving.
  useEffect(() => {
    const video = videoRef.current;
    return () => {
      const stream = video?.srcObject as MediaStream | null | undefined;
      stream?.getTracks().forEach(t => t.stop());
    };
  }, []);

  // Draw loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let raf = 0;
    let lastHud = 0;

    const frame = (now: number) => {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const sensor = sensorBasis.current;
      if (sensor) sensorSeen.current = true;
      const view: Basis = sensor ?? basisFromLook(manual.current.az, manual.current.el);
      const look = lookAngles(view.forward);
      if (now - lastHud > 150) {
        lastHud = now;
        setHud({ az: look.azimuth, el: look.elevation });
      }

      drawGrid(ctx, view, w, h);

      const out: Placed[] = [];
      const picked = selectedRef.current;
      let pointer: { sat: VisibleSat; turn: number } | null = null;
      for (const sat of satsRef.current) {
        const p = project(sat.azimuth_deg, sat.altitude_deg, view, w, h, FOV_V);
        const onScreen = p.inFront && p.x > -20 && p.x < w + 20 && p.y > -20 && p.y < h + 20;
        if (onScreen) {
          out.push({ sat, x: p.x, y: p.y });
          drawSat(ctx, sat, p.x, p.y, sat.name === picked);
        } else if (sat.name === picked) {
          pointer = { sat, turn: turnToward(look.azimuth, sat.azimuth_deg) };
        }
      }
      placed.current = out;
      if (pointer) drawPointer(ctx, pointer.sat, pointer.turn, look.elevation, w, h);
      drawReticle(ctx, w, h);

      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [sensorBasis]);

  // Drag to look (no sensors) and tap to pick a satellite.
  const onPointerDown = (e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, moved: false };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) d.moved = true;
    if (sensorBasis.current) return; // sensors are in charge
    const w = canvasRef.current?.clientHeight ?? 700;
    const degPerPx = FOV_V / w;
    manual.current = {
      az: normalizeDeg(manual.current.az - dx * degPerPx),
      el: Math.max(-90, Math.min(90, manual.current.el + dy * degPerPx)),
    };
    d.x = e.clientX;
    d.y = e.clientY;
  };
  const onPointerUp = (e: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!d || d.moved) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    let best: Placed | null = null;
    let bestD = TAP_RADIUS;
    for (const p of placed.current) {
      const dist = Math.hypot(p.x - x, p.y - y);
      if (dist < bestD) {
        best = p;
        bestD = dist;
      }
    }
    onSelect(best ? (best.sat.name === selectedRef.current ? null : best.sat.name) : null);
  };

  const chosen = sats.find(s => s.name === selected) ?? null;
  const usingSensors = status === "active" && sensorSeen.current;
  const insecure = typeof window !== "undefined" && !window.isSecureContext;

  // Portal: the sky panel's backdrop-filter would otherwise trap a position:fixed child.
  return createPortal(
    <div className="skyview" role="dialog" aria-label="Sky view">
      <video ref={videoRef} className={`skyview__video${cameraOn ? " is-on" : ""}`} playsInline muted />
      <canvas
        ref={canvasRef}
        className="skyview__canvas"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      />

      <div className="skyview__top">
        <button type="button" className="skyview__close" onClick={onClose} aria-label="Close sky view">
          ✕
        </button>
        <div className="skyview__heading">
          {compassPoint(hud.az)} {Math.round(hud.az)}° · {hud.el >= 0 ? "up" : "down"} {Math.abs(Math.round(hud.el))}°
        </div>
      </div>

      {!started && (
        <div className="skyview__card">
          <h3>📱 Sky view</h3>
          <p>
            Hold your phone up and satellites appear where they are in the real sky. The phone’s
            compass and tilt aim the view.
          </p>
          {insecure && (
            <p className="skyview__warn">
              This page isn’t secure (https), so the browser blocks the compass and camera. Drag to
              look around instead, or run <code>npm run dev:phone</code> and open the https address
              on your phone.
            </p>
          )}
          <label className="skyview__check">
            <input type="checkbox" checked={wantCamera} onChange={e => setWantCamera(e.target.checked)} />
            Show the camera behind the satellites
          </label>
          <button type="button" className="btn-primary" onClick={begin}>
            Start
          </button>
        </div>
      )}

      {started && (
        <div className="skyview__bottom">
          {cameraError && <div className="skyview__warn">{cameraError}</div>}
          {status === "denied" && <div className="skyview__warn">Motion sensors were refused. Drag to look around instead.</div>}
          {status === "unsupported" && <div className="skyview__warn">No motion sensors here. Drag to look around.</div>}
          {status === "insecure" && <div className="skyview__warn">The browser blocks sensors on non-https pages. Drag to look around.</div>}
          {usingSensors && !compassKnown && (
            <div className="skyview__warn">
              This browser can’t tell which way is north. Turn the slider until the heading above
              matches a compass app.
            </div>
          )}
          {usingSensors && (
            <label className="skyview__fix">
              Compass fix {headingFix > 0 ? "+" : ""}
              {headingFix}°
              {Math.abs(declinationDeg) >= 0.5 && (
                <small className="sky-muted"> (magnetic correction {declinationDeg > 0 ? "+" : ""}{declinationDeg.toFixed(0)}° applied)</small>
              )}
              <input
                type="range"
                min={-180}
                max={180}
                step={1}
                value={headingFix}
                onChange={e => setHeadingFix(Number(e.target.value))}
              />
            </label>
          )}
          {chosen ? (
            <div className="skyview__detail">
              <strong>{chosen.name}</strong>{" "}
              <span className="sky-muted">
                {Math.round(chosen.altitude_deg)}° up, towards {compassPoint(chosen.azimuth_deg)}
                {chosen.magnitude !== null && <> · mag {formatMag(chosen.magnitude)}</>} ·{" "}
                {STATUS_STYLE[chosen.status].label}
              </span>
            </div>
          ) : (
            <div className="skyview__hint">
              {sats.length === 0 ? "No satellites above your horizon right now." : "Tap a satellite to follow it."}
            </div>
          )}
        </div>
      )}
    </div>,
    document.body,
  );
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------
function drawGrid(ctx: CanvasRenderingContext2D, view: Basis, w: number, h: number) {
  ctx.lineWidth = 1;
  ctx.font = "12px system-ui, sans-serif";
  ctx.textAlign = "center";

  // altitude rings (30, 60) and the horizon, as dotted/solid lines
  for (const alt of [0, 30, 60]) {
    ctx.strokeStyle = alt === 0 ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.22)";
    ctx.setLineDash(alt === 0 ? [] : [4, 6]);
    ctx.beginPath();
    let pen = false;
    for (let az = 0; az <= 360; az += 3) {
      const p = project(az, alt, view, w, h, FOV_V);
      if (!p.inFront || Math.abs(p.x) > w * 4 || Math.abs(p.y) > h * 4) {
        pen = false;
        continue;
      }
      if (pen) ctx.lineTo(p.x, p.y);
      else ctx.moveTo(p.x, p.y);
      pen = true;
    }
    ctx.stroke();
    if (alt > 0) {
      const p = project(normalizeDeg(lookAngles(view.forward).azimuth), alt, view, w, h, FOV_V);
      if (p.inFront && p.y > 14 && p.y < h - 14) {
        ctx.fillStyle = "rgba(255,255,255,0.5)";
        ctx.fillText(`${alt}°`, w - 24, p.y - 4);
      }
    }
  }
  ctx.setLineDash([]);

  // compass labels on the horizon
  ctx.fillStyle = "#fff";
  ctx.font = "bold 14px system-ui, sans-serif";
  for (const [az, label] of POINTS) {
    const p = project(az, 0, view, w, h, FOV_V);
    if (!p.inFront || p.x < 10 || p.x > w - 10) continue;
    ctx.fillStyle = label === "N" ? "#ff6b6b" : "#fff";
    ctx.fillText(label, p.x, Math.min(Math.max(p.y - 8, 20), h - 12));
  }
}

function drawSat(ctx: CanvasRenderingContext2D, sat: VisibleSat, x: number, y: number, picked: boolean) {
  const color = STATUS_STYLE[sat.status].color;
  const r = sat.naked_eye ? 7 : 4.5;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  if (sat.status === "in_shadow") {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();
  } else {
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
  if (picked) {
    ctx.beginPath();
    ctx.arc(x, y, r + 8, 0, Math.PI * 2);
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  if (picked || sat.naked_eye) {
    ctx.font = `${picked ? "bold " : ""}13px system-ui, sans-serif`;
    ctx.textAlign = "left";
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(0,0,0,0.75)";
    ctx.strokeText(sat.name, x + r + 6, y + 4);
    ctx.fillStyle = "#fff";
    ctx.fillText(sat.name, x + r + 6, y + 4);
  }
}

function drawPointer(
  ctx: CanvasRenderingContext2D,
  sat: VisibleSat,
  turn: number,
  elevation: number,
  w: number,
  h: number,
) {
  const side = turn >= 0 ? 1 : -1;
  const x = side > 0 ? w - 18 : 18;
  const y = h / 2;
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.moveTo(x + 10 * side, y);
  ctx.lineTo(x - 6 * side, y - 12);
  ctx.lineTo(x - 6 * side, y + 12);
  ctx.closePath();
  ctx.fill();
  const up = Math.round(sat.altitude_deg - elevation);
  ctx.font = "bold 13px system-ui, sans-serif";
  ctx.textAlign = side > 0 ? "right" : "left";
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(0,0,0,0.75)";
  const text = `${sat.name}: turn ${turn >= 0 ? "right" : "left"} ${Math.round(Math.abs(turn))}°${
    Math.abs(up) > 5 ? `, ${up > 0 ? "up" : "down"} ${Math.abs(up)}°` : ""
  }`;
  const room = w - 70;
  ctx.strokeText(text, x - 18 * side, y + 5, room);
  ctx.fillText(text, x - 18 * side, y + 5, room);
}

function drawReticle(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.strokeStyle = "rgba(255,255,255,0.55)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(w / 2 - 10, h / 2);
  ctx.lineTo(w / 2 + 10, h / 2);
  ctx.moveTo(w / 2, h / 2 - 10);
  ctx.lineTo(w / 2, h / 2 + 10);
  ctx.stroke();
}
