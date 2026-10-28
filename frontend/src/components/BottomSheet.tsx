import { useEffect, useRef, useState, type ReactNode } from "react";
import "./bottom-sheet.css";

export type Snap = "peek" | "half" | "full";

type Props = {
  snap: Snap;
  onSnapChange: (snap: Snap) => void;
  /** the one line (or two) that stays visible when the sheet is down */
  summary: ReactNode;
  children: ReactNode;
};

const PEEK_PX = 88;
const ORDER: Snap[] = ["peek", "half", "full"];

function heights(area: number): Record<Snap, number> {
  return { peek: PEEK_PX, half: Math.round(area * 0.55), full: Math.max(PEEK_PX + 40, area - 8) };
}

/**
 * A phone bottom sheet with three resting heights. Drag the handle up or down (it snaps to
 * the nearest, with a little momentum), or tap it to open and close.
 */
export default function BottomSheet({ snap, onSnapChange, summary, children }: Props) {
  const ref = useRef<HTMLElement | null>(null);
  // the sheet lives inside the map area, so its heights follow that area, not the window
  const [viewport, setViewport] = useState(() => Math.round(window.innerHeight * 0.75));
  const [dragVisible, setDragVisible] = useState<number | null>(null);
  const drag = useRef<{ startY: number; startVisible: number; lastY: number; lastT: number; v: number; moved: boolean } | null>(null);

  useEffect(() => {
    const parent = ref.current?.parentElement;
    if (!parent) return;
    const measure = () => setViewport(parent.clientHeight);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(parent);
    return () => ro.disconnect();
  }, []);

  const h = heights(viewport);
  const fullH = h.full;
  const visible = dragVisible ?? h[snap];

  const onPointerDown = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { startY: e.clientY, startVisible: h[snap], lastY: e.clientY, lastT: e.timeStamp, v: 0, moved: false };
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dy = e.clientY - d.startY;
    if (Math.abs(dy) > 5) d.moved = true;
    const dt = Math.max(1, e.timeStamp - d.lastT);
    d.v = (e.clientY - d.lastY) / dt; // px per ms, positive = moving down
    d.lastY = e.clientY;
    d.lastT = e.timeStamp;
    if (d.moved) setDragVisible(Math.min(fullH, Math.max(PEEK_PX, d.startVisible - dy)));
  };

  const finish = (e: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (!d.moved) {
      // a tap: open from peek, otherwise close
      onSnapChange(snap === "peek" ? "half" : "peek");
      setDragVisible(null);
      return;
    }
    const projected = Math.min(fullH, Math.max(PEEK_PX, (dragVisible ?? d.startVisible) - d.v * 160));
    const nearest = ORDER.reduce((best, s) => (Math.abs(h[s] - projected) < Math.abs(h[best] - projected) ? s : best), snap);
    onSnapChange(nearest);
    setDragVisible(null);
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  };

  return (
    <section
      ref={ref}
      className={`sheet sheet--${snap}${dragVisible !== null ? " is-dragging" : ""}`}
      style={{ height: fullH, transform: `translateY(${fullH - visible}px)` }}
      aria-label="Satellite and sky details"
    >
      <div
        className="sheet__grab"
        role="button"
        tabIndex={0}
        aria-expanded={snap !== "peek"}
        aria-label={snap === "peek" ? "Open details" : "Close details"}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={finish}
        onPointerCancel={finish}
        onKeyDown={e => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSnapChange(snap === "peek" ? "half" : snap === "half" ? "full" : "peek");
          }
        }}
      >
        <span className="sheet__handle" />
        <div className="sheet__summary">{summary}</div>
      </div>
      <div className="sheet__body" style={{ maxHeight: Math.max(0, visible - PEEK_PX) }}>
        {children}
      </div>
    </section>
  );
}
