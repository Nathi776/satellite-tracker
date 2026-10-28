import { useCallback, useEffect, useMemo } from "react";
import { MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import {
  fetchGroundTrack,
  fetchSatelliteInfo,
  fetchSatellitePosition,
  fetchSatelliteView,
  type SatelliteInfo,
} from "../api";
import { useFavourites } from "../hooks/useFavourites";
import { useObserver } from "../hooks/useObserver";
import { usePolling } from "../hooks/usePolling";
import { useTicker } from "../hooks/useTicker";
import { groupColor } from "../utils/groups";
import { loadMapStyle, MAP_STYLES } from "../utils/mapStyles";
import { splitTrack } from "../utils/track";
import { formatDay } from "../utils/sky";
import { WhereToLook } from "./InfoPanel";
import ObserverMarker from "./ObserverMarker";
import { PassCard } from "./PassCard";
import SelectedSatMarker from "./SelectedSatMarker";
import "./map-ui.css";
import "./sky.css";
import "./satellite-page.css";

const GROUP_LABEL: Record<string, string> = {
  stations: "Stations",
  africa: "Africa",
  weather: "Weather",
  navigation: "Navigation",
  starlink: "Starlink",
  oneweb: "OneWeb",
  comms: "Comms",
  other: "Other",
};

const fmt = (n: number) => Math.round(n).toLocaleString();

function Follow({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap();
  // centre once when the position first arrives; after that the user is in charge
  useEffect(() => {
    map.setView([lat, lon], 3, { animate: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);
  return null;
}

function Facts({ info }: { info: SatelliteInfo }) {
  const old = info.element_age_days > 7;
  return (
    <dl className="info__grid sp-facts">
      <dt>NORAD ID</dt>
      <dd>{info.norad_id}</dd>
      <dt>Group</dt>
      <dd>
        {GROUP_LABEL[info.group] ?? info.group}
        {info.country ? ` · ${info.country}` : ""}
      </dd>
      <dt>Orbit height</dt>
      <dd>
        {fmt(info.perigee_km)}–{fmt(info.apogee_km)} km
      </dd>
      <dt>Inclination</dt>
      <dd>{info.inclination_deg}°</dd>
      <dt>Period</dt>
      <dd>
        {info.period_min.toFixed(1)} min <small>({info.revs_per_day.toFixed(2)} orbits a day)</small>
      </dd>
      <dt>Eccentricity</dt>
      <dd>{info.eccentricity}</dd>
      <dt>Elements from</dt>
      <dd>
        {formatDay(info.epoch_utc)} <small>({info.element_age_days.toFixed(1)} days old)</small>
        {old && <small className="sp-warn"> · positions get less accurate as this ages</small>}
      </dd>
    </dl>
  );
}

export default function SatellitePage({ name }: { name: string }) {
  const nowMs = useTicker(1000);
  const { location, requestLocation } = useObserver();
  const { isFavourite, toggle } = useFavourites();
  const mapStyle = MAP_STYLES.find(m => m.id === loadMapStyle()) ?? MAP_STYLES[0];

  const infoFetcher = useCallback((s: AbortSignal) => fetchSatelliteInfo(name, s), [name]);
  const info = usePolling(infoFetcher, 5 * 60_000);

  const posFetcher = useCallback((s: AbortSignal) => fetchSatellitePosition(name, s), [name]);
  const posPoll = usePolling(posFetcher, 2000);
  const pos = posPoll.data?.position ?? null;

  const viewFetcher = useMemo(
    () => (location ? (s: AbortSignal) => fetchSatelliteView(name, location.lat, location.lon, s) : null),
    [location, name],
  );
  const view = usePolling(viewFetcher, 10_000);

  const period = info.data?.period_min ?? 90;
  const futureFetcher = useCallback(
    (s: AbortSignal) =>
      fetchGroundTrack(name, { minutes: Math.min(1440, Math.ceil(period * 1.25)), step: Math.max(1, period / 90) }, s),
    [name, period],
  );
  const future = usePolling(futureFetcher, 60_000);
  const pastFetcher = useCallback(
    (s: AbortSignal) => {
      const back = Math.min(720, Math.ceil(period * 0.5));
      return fetchGroundTrack(name, { at: Date.now() - back * 60_000, minutes: back, step: Math.max(1, back / 60) }, s);
    },
    [name, period],
  );
  const past = usePolling(pastFetcher, 60_000);

  const toPoints = (t?: { lat: number; lon: number }[]) => (t ?? []).map(p => [p.lat, p.lon]);
  const group = info.data?.group;
  const fav = isFavourite(name);
  const notFound = info.error?.startsWith("404");

  useEffect(() => {
    document.title = `${name} · Satellite Tracker`;
    return () => {
      document.title = "Satellite Tracker";
    };
  }, [name]);

  // move the marker along its path between refreshes
  const elapsed = posPoll.receivedAt ? Math.max(0, (nowMs - posPoll.receivedAt) / 1000) : 0;
  const lat = pos ? pos.lat + (pos.lat_rate ?? 0) * elapsed : 0;
  const lon = pos ? pos.lon + (pos.lon_rate ?? 0) * elapsed : 0;

  return (
    <div className="sp">
      <header className="sp-head">
        <a className="sp-back" href="#/">
          ← Map
        </a>
        <div className="sp-title">
          <h1>{name}</h1>
          {group && (
            <span className="info__group" style={{ ["--chip" as string]: groupColor(group) }}>
              {GROUP_LABEL[group] ?? group}
              {info.data?.country ? ` · ${info.data.country}` : ""}
            </span>
          )}
        </div>
        <button
          type="button"
          className={`sp-star${fav ? " is-on" : ""}`}
          aria-pressed={fav}
          onClick={() => toggle(name)}
        >
          {fav ? "★ Favourite" : "☆ Add to favourites"}
        </button>
      </header>

      {notFound ? (
        <p className="sp-missing">
          “{name}” isn't in the catalogue right now. <a href="#/">Back to the map</a>
        </p>
      ) : (
        <div className="sp-grid">
          <section className="sp-map" aria-label="Where it is">
            <MapContainer center={[0, 0]} zoom={2} minZoom={1} worldCopyJump>
              <TileLayer
                key={mapStyle.id}
                attribution={mapStyle.attribution}
                url={mapStyle.url}
                subdomains={mapStyle.subdomains ?? "abc"}
                maxZoom={mapStyle.maxZoom}
              />
              {pos && <Follow lat={pos.lat} lon={pos.lon} />}
              {splitTrack(toPoints(past.data?.track)).map((seg, i) => (
                <Polyline
                  key={`p${i}`}
                  positions={seg as [number, number][]}
                  pathOptions={{ color: "#5eead4", weight: 2, opacity: 0.55, dashArray: "3 7", interactive: false }}
                />
              ))}
              {splitTrack(toPoints(future.data?.track)).map((seg, i) => (
                <Polyline
                  key={`f${i}`}
                  positions={seg as [number, number][]}
                  pathOptions={{ color: "#2dd4bf", weight: 2.5, opacity: 0.95, interactive: false }}
                />
              ))}
              {location && <ObserverMarker lat={location.lat} lon={location.lon} />}
              {pos && <SelectedSatMarker name={name} lat={lat} lon={lon} group={group} />}
            </MapContainer>
          </section>

          <div className="sp-side">
            {info.data && (
              <section className="info sp-card">
                <h2>About</h2>
                <p className="sp-about">{info.data.description}</p>
              </section>
            )}

            <section className="info sp-card">
              {!location ? (
                <>
                  <h2>Where to look</h2>
                  <p className="info__note">Share your location to see where to look and when it passes over you.</p>
                  <button type="button" className="btn-primary" onClick={requestLocation}>
                    📍 Use my location
                  </button>
                </>
              ) : view.data ? (
                <WhereToLook view={view.data} receivedAt={view.receivedAt} nowMs={nowMs} />
              ) : (
                <p className="info__note">{view.error ? `⚠ ${view.error}` : "Working out where to look…"}</p>
              )}
            </section>

            <section className="info sp-card">
              <h2>Right now</h2>
              {pos ? (
                <dl className="info__grid">
                  <dt>Over</dt>
                  <dd>
                    {Math.abs(lat).toFixed(2)}° {lat >= 0 ? "N" : "S"}, {Math.abs(lon).toFixed(2)}° {lon >= 0 ? "E" : "W"}
                  </dd>
                  <dt>Altitude</dt>
                  <dd>{pos.alt_km !== undefined ? `${fmt(pos.alt_km)} km` : "–"}</dd>
                  <dt>Speed</dt>
                  <dd>
                    {pos.speed_kms !== undefined ? (
                      <>
                        {pos.speed_kms.toFixed(2)} km/s <small>({fmt(pos.speed_kms * 3600)} km/h)</small>
                      </>
                    ) : (
                      "–"
                    )}
                  </dd>
                  {pos.footprint_km ? (
                    <>
                      <dt>Sees</dt>
                      <dd>within {fmt(pos.footprint_km)} km</dd>
                    </>
                  ) : null}
                </dl>
              ) : (
                <p className="info__note">{posPoll.error ? `⚠ ${posPoll.error}` : "Loading…"}</p>
              )}
            </section>

            <section className="info sp-card">
              <h2>Orbit</h2>
              {info.data ? <Facts info={info.data} /> : <p className="info__note">{info.error ? `⚠ ${info.error}` : "Loading…"}</p>}
            </section>
          </div>

          <section className="info sp-card sp-passes">
            <h2>Next passes over you</h2>
            {!location ? (
              <p className="info__note">Share your location to see the passes.</p>
            ) : !view.data ? (
              <p className="info__note">Working it out…</p>
            ) : view.data.passes.length === 0 ? (
              <p className="info__note">No passes above 10° in the next 48 hours.</p>
            ) : (
              <div className="sp-pass-list">
                {view.data.passes.map(p => (
                  <PassCard key={p.rise_time_utc} pass={p} nowMs={nowMs} />
                ))}
              </div>
            )}
            {view.data && view.data.passes.length > 0 && (
              <small className="sky-muted">Times are shown in your local time.</small>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
