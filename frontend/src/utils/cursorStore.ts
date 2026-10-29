// Where the pointer is on the map. Kept outside React state so that moving the mouse
// re-renders only the status bar, not the whole map page.
export type Cursor = { lat: number; lon: number } | null;

let current: Cursor = null;
const listeners = new Set<() => void>();

export const cursorStore = {
  get: () => current,
  set(next: Cursor) {
    current = next;
    listeners.forEach(l => l());
  },
  subscribe(l: () => void) {
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  },
};
