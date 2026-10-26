import { useCallback, useEffect, useRef, useState } from "react";
import {
  blendBasis,
  deviceBasis,
  lookAngles,
  normalizeDeg,
  turnToward,
  type Basis,
} from "../utils/orientation";

export type SensorStatus = "idle" | "active" | "denied" | "unsupported" | "insecure";

type IOSOrientationEvent = DeviceOrientationEvent & { webkitCompassHeading?: number };
type IOSPermissionApi = { requestPermission?: () => Promise<"granted" | "denied"> };

const SMOOTHING = 0.3;

/**
 * Where the phone is pointing, as a Basis (see utils/orientation).
 *
 * The basis lives in a ref and is updated at sensor rate, so reading it does not re-render
 * React. `compassKnown` says whether the heading is relative to north; when it is not (some
 * browsers only give a relative heading) the user must set `headingFixDeg` by hand.
 */
export function useDeviceOrientation(headingFixDeg: number) {
  const [status, setStatus] = useState<SensorStatus>("idle");
  const [compassKnown, setCompassKnown] = useState(true);
  const basis = useRef<Basis | null>(null);
  const fix = useRef(headingFixDeg);
  const iosOffset = useRef<number | null>(null);
  const sawAbsolute = useRef(false);
  const stop = useRef<(() => void) | null>(null);

  useEffect(() => {
    fix.current = headingFixDeg;
  }, [headingFixDeg]);

  useEffect(() => () => stop.current?.(), []);

  const start = useCallback(async () => {
    if (typeof window === "undefined" || typeof DeviceOrientationEvent === "undefined") {
      setStatus("unsupported");
      return;
    }
    if (!window.isSecureContext) {
      setStatus("insecure");
      return;
    }

    // iOS asks for permission, and only inside a tap.
    const ios = DeviceOrientationEvent as unknown as IOSPermissionApi;
    if (typeof ios.requestPermission === "function") {
      try {
        if ((await ios.requestPermission()) !== "granted") {
          setStatus("denied");
          return;
        }
      } catch {
        setStatus("denied");
        return;
      }
    }

    const handle = (e: DeviceOrientationEvent, absolute: boolean) => {
      if (e.alpha === null || e.beta === null || e.gamma === null) return;
      if (!absolute && sawAbsolute.current) return; // the absolute stream wins when present

      let alpha = e.alpha;
      const heading = (e as IOSOrientationEvent).webkitCompassHeading;
      if (typeof heading === "number" && !Number.isNaN(heading)) {
        // iOS: alpha is relative to wherever the phone was when started; webkitCompassHeading
        // is the real compass heading. Learn the difference while the phone is not pointing
        // at the sky or ground (where the heading is ill-defined).
        const raw = lookAngles(deviceBasis(alpha, e.beta, e.gamma).forward);
        if (Math.abs(raw.elevation) < 70) {
          const off = turnToward(raw.azimuth, heading);
          const prev = iosOffset.current;
          iosOffset.current = prev === null ? off : prev + turnToward(prev, off) * 0.1;
        }
        alpha -= iosOffset.current ?? 0;
        setCompassKnown(true);
      } else if (absolute || e.absolute) {
        setCompassKnown(true);
      } else if (!sawAbsolute.current) {
        setCompassKnown(false);
      }

      const next = deviceBasis(normalizeDeg(alpha - fix.current), e.beta, e.gamma);
      basis.current = blendBasis(basis.current, next, SMOOTHING);
    };

    const onAbsolute = (e: Event) => {
      sawAbsolute.current = true;
      handle(e as DeviceOrientationEvent, true);
    };
    const onRelative = (e: Event) => handle(e as DeviceOrientationEvent, false);

    window.addEventListener("deviceorientationabsolute", onAbsolute);
    window.addEventListener("deviceorientation", onRelative);
    stop.current = () => {
      window.removeEventListener("deviceorientationabsolute", onAbsolute);
      window.removeEventListener("deviceorientation", onRelative);
    };
    setStatus("active");
  }, []);

  return { status, compassKnown, basis, start };
}
