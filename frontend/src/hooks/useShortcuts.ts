import { useEffect, useRef } from "react";

/** Single-key shortcuts (no modifiers). Ignored while typing in a field. */
export function useShortcuts(handlers: Record<string, () => void>) {
  const ref = useRef(handlers);
  ref.current = handlers;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      const typing = !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      // Escape still works from a field (it leaves the field), everything else waits
      if (typing && key !== "Escape") return;
      const fn = ref.current[key];
      if (!fn) return;
      e.preventDefault();
      fn();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
