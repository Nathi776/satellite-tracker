export type MapStyleId = "dark" | "satellite" | "street";

export type MapStyle = {
  id: MapStyleId;
  label: string;
  url: string;
  attribution: string;
  subdomains?: string;
  maxZoom: number;
  /** is the map dark enough for white labels / glow to read well */
  dark: boolean;
};

export const MAP_STYLES: MapStyle[] = [
  {
    id: "dark",
    label: "Dark",
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attribution: "© OpenStreetMap contributors © CARTO",
    subdomains: "abcd",
    maxZoom: 19,
    dark: true,
  },
  {
    id: "satellite",
    label: "Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    maxZoom: 18,
    dark: true,
  },
  {
    id: "street",
    label: "Street",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: "© OpenStreetMap contributors",
    subdomains: "abc",
    maxZoom: 19,
    dark: false,
  },
];

const KEY = "satellite-tracker:map-style";

export function loadMapStyle(): MapStyleId {
  try {
    const v = window.localStorage.getItem(KEY);
    if (v === "dark" || v === "satellite" || v === "street") return v;
  } catch {
    /* storage can be blocked; the default is fine */
  }
  return "dark";
}

export function saveMapStyle(id: MapStyleId) {
  try {
    window.localStorage.setItem(KEY, id);
  } catch {
    /* ignore */
  }
}
