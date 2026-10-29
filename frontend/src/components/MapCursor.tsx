import { useMapEvents } from "react-leaflet";
import { cursorStore } from "../utils/cursorStore";

/** Reports the pointer position (wrapped to -180..180) to the status bar. */
export default function MapCursor() {
  useMapEvents({
    mousemove: e => {
      const lon = ((((e.latlng.lng + 180) % 360) + 360) % 360) - 180;
      cursorStore.set({ lat: e.latlng.lat, lon });
    },
    mouseout: () => cursorStore.set(null),
  });
  return null;
}
