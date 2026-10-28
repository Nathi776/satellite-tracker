import { useCallback, useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polygon,
  Polyline,
  useMap,
  useMapEvents,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import InfoPanel from "./InfoPanel";
import BottomCards from "./BottomCards";
import SkyLabels from "./SkyLabels";
import { useMediaQuery } from "../hooks/useMediaQuery";
import SkyPanel, { type SkyTab } from "./SkyPanel";
import SatelliteLayer from "./SatelliteLayer";
import GroupChips from "./GroupChips";
import TimeControl from "./TimeControl";
import NightShade from "./NightShade";
import ObserverMarker from "./ObserverMarker";
import SelectedSatMarker from "./SelectedSatMarker";
import MapStyleSwitch from "./MapStyleSwitch";
import UtcClock from "./UtcClock";
import { MAP_STYLES, loadMapStyle, saveMapStyle, type MapStyleId } from "../utils/mapStyles";
import { useObserver } from "../hooks/useObserver";
import { useDebounce } from "../hooks/useDebounce";
import { usePolling } from "../hooks/usePolling";
import { useTicker } from "../hooks/useTicker";
import {
  fetchGroundTrack,
  fetchGroups,
  fetchPositions,
  fetchSatelliteView,
  fetchVisibility,
  type VisibilityStatus,
  type VisibleSat,
} from "../api";
import {
  STATUS_STYLE,
  compassPoint,
  formatMag,
  moveInSky,
  moveOnMap,
} from "../utils/sky";
import { footprintPolygons } from "../utils/geo";
import { groupColor } from "../utils/groups";
import "./sky.css";
import "./map-ui.css";

// -------------------
// Fix marker icons
// -------------------
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Satellites above the observer's horizon, coloured by whether they can be seen.
function dotIcon(status: VisibilityStatus, big: boolean, selected: boolean) {
  const size = big ? 18 : 12;
  const color = STATUS_STYLE[status].color;
  const fill = status === "in_shadow" ? "transparent" : color;
  const ring = selected ? ";outline:2px solid #fff;outline-offset:2px" : "";
  return L.divIcon({
    className: "",
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${fill};border:2px solid ${
      big ? "#fff" : color
    };box-shadow:0 0 ${big ? 10 : 4}px ${color}${ring}"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// How often the API is asked again; in between, satellites are moved along their rates.
const VISIBILITY_REFRESH_MS = 5000;
const SAT_VIEW_REFRESH_MS = 10000;
const POSITIONS_REFRESH_MS = 10000;
const TRACK_REFRESH_MS = 60000;
// A fixed moment in time doesn't change, so there is little reason to ask again.
const TIME_TRAVEL_REFRESH_MS = 10 * 60 * 1000;
const STALE_AFTER_S = 20;
const LIMITS = [100, 300, 1000, 2000];
const TIME_TRAVEL_HOURS = 24;

// -------------------
// Helpers
// -------------------
/** Split a ground track where it wraps across the ±180° meridian, so Leaflet
 *  doesn't draw a line straight across the whole map. */
function splitTrack(points: number[][]) {
  if (points.length === 0) return [];

  const segments: number[][][] = [];
  let current: number[][] = [points[0]];

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const curr = points[i];

    if (Math.abs(curr[1] - prev[1]) > 180) {
      segments.push(current);
      current = [];
    }
    current.push(curr);
  }

  if (current.length) segments.push(current);
  return segments;
}

/** Fly to Africa when that filter is chosen. */
function FlyToGroup({ group }: { group: string }) {
  const map = useMap();
  useEffect(() => {
    if (group === "africa") map.flyTo([2, 20], 3, { duration: 0.8 });
  }, [group, map]);
  return null;
}

/**
 * Leaflet only notices the window resizing, not its own container. This page's layout does
 * change under it (the filter chips appear once /groups loads, the header wraps on a phone),
 * and without a nudge the map keeps its old size: dots then sit offset from where they belong
 * and part of the map is cut off.
 */
function ResizeWatcher() {
  const map = useMap();
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

/** Clicking empty map deselects the satellite. */
function MapClicks({ onClick }: { onClick: () => void }) {
  useMapEvents({ click: onClick });
  return null;
}

// -------------------
// Component
// -------------------
export default function SatelliteMap() {
  // One tick per second drives all animation.
  const nowMs = useTicker(1000);

  const [search, setSearch] = useState("");
  // Wait until the user stops typing before hitting the API.
  const debouncedSearch = useDebounce(search.trim(), 350);

  const [group, setGroup] = useState("all");
  const [limit, setLimit] = useState(300);
  const [selectedName, setSelectedName] = useState<string | null>(null); // map dot
  const [selectedSky, setSelectedSky] = useState<string | null>(null); // radar / list
  const [nakedEyeOnly, setNakedEyeOnly] = useState(true);
  const [skyTab, setSkyTab] = useState<SkyTab>("now");
  const [showTrack, setShowTrack] = useState(true);
  // desktop layout: detail card on the right; wide screens also get the card row under the map
  const wide = useMediaQuery("(min-width: 721px)");
  const cardRow = useMediaQuery("(min-width: 1000px)");
  const [mapStyleId, setMapStyleId] = useState<MapStyleId>(loadMapStyle);
  const mapStyle = MAP_STYLES.find(m => m.id === mapStyleId) ?? MAP_STYLES[0];
  const changeMapStyle = useCallback((id: MapStyleId) => {
    setMapStyleId(id);
    saveMapStyle(id);
  }, []);

  // Time travel: offsetMin is what the slider shows; atMs is the moment it means. The
  // moment is fixed when the slider moves (in the event handler), so it doesn't creep forward.
  const [travel, setTravel] = useState<{ offsetMin: number; atMs: number | null }>({
    offsetMin: 0,
    atMs: null,
  });
  const settledTravel = useDebounce(travel, 250);
  const travelAt = settledTravel.atMs;
  const onTravelChange = useCallback((offsetMin: number) => {
    setTravel({ offsetMin, atMs: offsetMin === 0 ? null : Date.now() + offsetMin * 60_000 });
  }, []);

  const { location, requestLocation } = useObserver();

  // -------------------
  // Live data
  // -------------------
  const groupsPolled = usePolling(fetchGroups, 5 * 60 * 1000);
  const groups = groupsPolled.data ?? [];
  const groupLabel = (id?: string) => groups.find(g => g.id === id)?.label;

  const positionsFetcher = useCallback(
    (signal: AbortSignal) =>
      fetchPositions({ search: debouncedSearch, group, limit, at: travelAt }, signal),
    [debouncedSearch, group, limit, travelAt],
  );
  const positions = usePolling(
    positionsFetcher,
    travelAt ? TIME_TRAVEL_REFRESH_MS : POSITIONS_REFRESH_MS,
  );

  const visibilityFetcher = useMemo(
    () =>
      location
        ? (signal: AbortSignal) => fetchVisibility(location.lat, location.lon, 48, signal)
        : null,
    [location],
  );
  const visibility = usePolling(visibilityFetcher, VISIBILITY_REFRESH_MS);

  // Seconds since each data set was computed: time in the browser since it arrived,
  // plus how old the server said it already was. Frozen while viewing another time.
  const positionsElapsed =
    positions.receivedAt && !travelAt ? (nowMs - positions.receivedAt) / 1000 : 0;
  const visibilityElapsed = visibility.receivedAt
    ? (nowMs - visibility.receivedAt) / 1000 + (visibility.data?.age_seconds ?? 0)
    : 0;

  const livePositions = useMemo(
    () => (positions.data ?? []).map(s => moveOnMap(s, positionsElapsed)),
    [positions.data, positionsElapsed],
  );

  // Everything above the horizon, moved to this instant. Anything that has set since the
  // last refresh drops out until the next one.
  const liveSats = useMemo(
    () =>
      (visibility.data?.visible_now ?? [])
        .map(s => moveInSky(s, visibilityElapsed))
        .filter((s): s is VisibleSat => s !== null),
    [visibility.data, visibilityElapsed],
  );

  // The green "above you" dots are live, so they would contradict a map showing another time.
  const timeTravelling = travelAt !== null;
  const mapSats = timeTravelling ? [] : nakedEyeOnly ? liveSats.filter(s => s.naked_eye) : liveSats;

  const selectedPos = livePositions.find(s => s.name === selectedName) ?? null;

  // Where to look for the selected satellite from here (live only: it is "now" for you).
  const viewName = selectedPos?.name ?? null;
  const viewFetcher = useMemo(
    () =>
      location && viewName && !travelAt
        ? (signal: AbortSignal) => fetchSatelliteView(viewName, location.lat, location.lon, signal)
        : null,
    [location, viewName, travelAt],
  );
  const satView = usePolling(viewFetcher, SAT_VIEW_REFRESH_MS);
  // ignore data that belongs to the previously selected satellite
  const viewData = satView.data && satView.data.name === viewName ? satView.data : null;

  const visibilityAge = visibility.receivedAt
    ? Math.round((nowMs - visibility.receivedAt) / 1000)
    : null;
  const stale =
    visibility.error !== null || (visibilityAge !== null && visibilityAge > STALE_AFTER_S);

  const error = visibility.error ?? positions.error ?? groupsPolled.error;

  // -------------------
  // Orbit of the selected satellite (or of the one being searched for)
  // -------------------
  const trackName = selectedPos?.name ?? (debouncedSearch || null);
  const trackMinutes = selectedPos?.period_min
    ? Math.min(1440, Math.ceil(selectedPos.period_min * 1.25))
    : 90;

  const trackFetcher = useMemo(
    () =>
      trackName
        ? (signal: AbortSignal) =>
            fetchGroundTrack(
              trackName,
              {
                at: travelAt,
                minutes: trackMinutes,
                step: Math.max(1, Math.round(trackMinutes / 150)),
              },
              signal,
            )
        : null,
    [trackName, trackMinutes, travelAt],
  );
  const track = usePolling(trackFetcher, travelAt ? TIME_TRAVEL_REFRESH_MS : TRACK_REFRESH_MS);
  // A failed request (e.g. 404 for a search matching nothing) means no track, not the old one.
  const trackPoints =
    trackFetcher && track.data && !track.error
      ? track.data.track.map(p => [p.lat, p.lon])
      : [];

  // Where the satellite has just been: the same orbit, behind it.
  const pastMinutes = Math.min(720, Math.ceil((selectedPos?.period_min ?? 90) * 0.5));
  const pastFetcher = useMemo(
    () =>
      trackName
        ? (signal: AbortSignal) =>
            fetchGroundTrack(
              trackName,
              {
                at: (travelAt ?? Date.now()) - pastMinutes * 60_000,
                minutes: pastMinutes,
                step: Math.max(1, Math.round(pastMinutes / 80)),
              },
              signal,
            )
        : null,
    [trackName, pastMinutes, travelAt],
  );
  const pastTrack = usePolling(pastFetcher, travelAt ? TIME_TRAVEL_REFRESH_MS : TRACK_REFRESH_MS);
  const pastPoints =
    pastFetcher && pastTrack.data && !pastTrack.error
      ? pastTrack.data.track.map(p => [p.lat, p.lon])
      : [];

  const footprint = useMemo(
    () =>
      selectedPos?.footprint_km
        ? footprintPolygons(selectedPos.lat, selectedPos.lon, selectedPos.footprint_km)
        : [],
    [selectedPos],
  );

  // How many are on the map, out of how many there are in this group
  const groupTotal = groups.find(g => g.id === group)?.count;
  const shownNote = debouncedSearch
    ? `${livePositions.length} match${livePositions.length === 1 ? "" : "es"}`
    : groupTotal !== undefined && groupTotal > livePositions.length
      ? `Showing ${livePositions.length.toLocaleString()} of ${groupTotal.toLocaleString()}`
      : `${livePositions.length.toLocaleString()} shown`;

  // -------------------
  // UI
  // -------------------
  return (
    <div className={`app${selectedPos ? " app--selected" : ""}`}>
      {/* HEADER */}
      <header className="app-header">
        <div className="app-header__top">
          <h2 className="brand">🛰 Satellite Tracker</h2>
          <UtcClock nowMs={nowMs} travelAtMs={travelAt} stale={stale} />

          <div className="searchbox">
            <span aria-hidden="true">🔍</span>
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search satellite (ISS, ZACUBE...)"
              aria-label="Search satellites"
            />
          </div>

          <button
            type="button"
            className="btn-primary"
            onClick={requestLocation}
            aria-label={location ? "Update my location" : "Use my location"}
          >
            <span aria-hidden="true">📍</span>
            <span className="btn-label">{location ? "Update My Location" : "Use My Location"}</span>
          </button>
        </div>

        <div className="app-header__row">
          <GroupChips groups={groups} active={group} onChange={setGroup} />
          <span className="shown-note shown-note--count" aria-live="polite">
            {shownNote}
          </span>
          <label className="shown-note">
            <span className="limit-label">Show up to</span>{" "}
            <select value={limit} onChange={e => setLimit(Number(e.target.value))}>
              {LIMITS.map(n => (
                <option key={n} value={n}>
                  {n.toLocaleString()}
                </option>
              ))}
            </select>
          </label>
          {error && (
            <span className="header-error" role="alert">
              ⚠ {error}
            </span>
          )}
        </div>
      </header>

      <div className="map-area">
        {/* MAP */}
        <MapContainer center={[0, 0]} zoom={2} minZoom={2} className={mapStyle.dark ? "map--dark" : undefined}>
          <TileLayer
            key={mapStyle.id}
            attribution={mapStyle.attribution}
            url={mapStyle.url}
            subdomains={mapStyle.subdomains ?? "abc"}
            maxZoom={mapStyle.maxZoom}
          />
          <NightShade timeMs={travelAt ?? nowMs} style={mapStyle.id} />
          <ResizeWatcher />
          <FlyToGroup group={group} />
          <MapClicks onClick={() => setSelectedName(null)} />

          {/* What the selected satellite can see */}
          {footprint.length > 0 && selectedPos && (
            <Polygon
              positions={footprint}
              pathOptions={{
                color: groupColor(selectedPos.group),
                weight: 1.5,
                fillOpacity: 0.1,
                interactive: false,
              }}
            />
          )}

          {/* All satellites: dots on a single canvas, moving live */}
          <SatelliteLayer
            sats={livePositions}
            selectedName={selectedName}
            onSelect={setSelectedName}
          />

          {/* Observer */}
          {!timeTravelling && wide && <SkyLabels sats={mapSats} skip={selectedPos?.name ?? null} onSelect={n => { setSelectedSky(n); setSelectedName(n); }} />}

          {location && <ObserverMarker lat={location.lat} lon={location.lon} />}

          {selectedPos && (
            <SelectedSatMarker
              name={selectedPos.name}
              lat={selectedPos.lat}
              lon={selectedPos.lon}
              group={selectedPos.group}
            />
          )}

          {/* Satellites above your horizon, coloured by visibility */}
          {mapSats.map(sat => (
            <Marker
              key={`sky-${sat.name}`}
              position={[sat.lat, sat.lon]}
              icon={dotIcon(sat.status, sat.naked_eye, sat.name === selectedSky)}
              zIndexOffset={sat.naked_eye ? 1000 : 0}
              eventHandlers={{
                click: () => setSelectedSky(sat.name),
              }}
            >
              <Popup>
                <strong>{sat.name}</strong>
                <br />
                {STATUS_STYLE[sat.status].label}
                <br />
                Elevation: {sat.altitude_deg.toFixed(0)}° · {compassPoint(sat.azimuth_deg)} (
                {sat.azimuth_deg.toFixed(0)}°)
                <br />
                Distance: {Math.round(sat.distance_km).toLocaleString()} km
                {sat.magnitude !== null && (
                  <>
                    <br />
                    Est. magnitude: {formatMag(sat.magnitude)}
                  </>
                )}
              </Popup>
            </Marker>
          ))}

          {/* Orbit: where it has been (dashed, faint) and where it is going (solid) */}
          {(showTrack || !selectedPos) && splitTrack(pastPoints).map((seg, i) => (
            <Polyline
              key={`past-${i}`}
              positions={seg as [number, number][]}
              pathOptions={{ color: "#5eead4", weight: 2, opacity: 0.55, dashArray: "3 7", interactive: false }}
            />
          ))}
          {(showTrack || !selectedPos) && splitTrack(trackPoints).map((seg, i) => (
            <Polyline
              key={`future-${i}`}
              positions={seg as [number, number][]}
              pathOptions={{ color: "#2dd4bf", weight: 2.5, opacity: 0.95, interactive: false }}
            />
          ))}
        </MapContainer>

        <MapStyleSwitch value={mapStyleId} onChange={changeMapStyle} />

        {/* Your sky: outside the map so it isn't tied to Leaflet's layout */}
        {(() => {
          const skyBlock = visibility.data ? (
            <SkyPanel
              visibility={visibility.data}
              sats={liveSats}
              nakedEyeOnly={nakedEyeOnly}
              onNakedEyeOnlyChange={setNakedEyeOnly}
              nowMs={nowMs}
              ageSeconds={visibilityAge}
              stale={stale}
              selected={selectedSky}
              onSelect={setSelectedSky}
              tab={skyTab}
              onTabChange={setSkyTab}
            />
          ) : (
            <div className="sky-hint">
              {location ? (
                visibility.error ? (
                  <>⚠ Couldn’t load your sky: {visibility.error}</>
                ) : (
                  <>Working out what’s above you…</>
                )
              ) : (
                <>
                  📍 Tap <strong>Use My Location</strong> to see which satellites are above you,
                  whether you can see them, and when the next pass is.
                </>
              )}
            </div>
          );

          const infoBlock = (
            <InfoPanel
              satellite={selectedPos}
              hasLocation={!!location}
              timeTravel={travelAt !== null}
              view={viewData}
              viewReceivedAt={satView.receivedAt}
              nowMs={nowMs}
              groupLabel={groupLabel(selectedPos?.group)}
              onClose={() => setSelectedName(null)}
              showTrack={wide ? showTrack : undefined}
              onShowTrackChange={wide ? setShowTrack : undefined}
            />
          );

          const timeBlock = (
            <TimeControl
              offsetMin={travel.offsetMin}
              onChange={onTravelChange}
              shownAtMs={travelAt}
              maxHours={TIME_TRAVEL_HOURS}
            />
          );

          // Wide screens: one column on the right (the selected satellite, else your sky).
          // Phones: your sky docks to the bottom, the selected satellite and time pill sit on top.
          return wide ? (
            <>
              <div className={`right-stack${selectedPos ? " right-stack--selected" : ""}`}>
                {infoBlock}
                {skyBlock}
              </div>
              <div className="left-stack">{timeBlock}</div>
            </>
          ) : (
            <>
              {skyBlock}
              <div className="left-stack">
                {infoBlock}
                {timeBlock}
              </div>
            </>
          );
        })()}
      </div>

      {cardRow && visibility.data && !timeTravelling && (
        <BottomCards
          sats={liveSats}
          passes={visibility.data.next_passes}
          nowMs={nowMs}
          selected={selectedSky ?? selectedName}
          onSelect={name => {
            setSelectedSky(name);
            setSelectedName(name);
          }}
          onViewAll={tab => {
            setSkyTab(tab);
            setSelectedName(null);
          }}
        />
      )}
    </div>
  );
}
