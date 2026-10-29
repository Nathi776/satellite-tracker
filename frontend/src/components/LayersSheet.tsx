import { useEffect, type ReactNode } from "react";
import "./layers-panel.css";

/** Phone: the layers slide up over the map; tapping outside or pressing Back/Escape closes them. */
export default function LayersSheet({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="layers-sheet" role="dialog" aria-modal="true" aria-label="Layers">
      <button type="button" className="layers-sheet__backdrop" aria-label="Close layers" onClick={onClose} />
      <div className="layers-sheet__body">{children}</div>
    </div>
  );
}
