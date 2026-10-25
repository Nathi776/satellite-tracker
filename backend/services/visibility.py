"""What an observer can see: satellites above the horizon now, and upcoming passes."""
import math
import threading
import time
from datetime import timedelta

from skyfield.api import wgs84

from backend import config
from backend.services import satellites as catalog
from backend.services import tle_service
from backend.services.satellites import ts

MIN_PASS_ELEVATION_DEG = 10.0
PASS_HOURS_AHEAD = 24
MAX_PASSES = 10

_cache_lock = threading.Lock()
_cache = {}  # key -> (computed_at_monotonic, result)


def _observer(lat, lon, elevation_m=0.0):
    return wgs84.latlon(lat, lon, elevation_m=elevation_m)


def compute_visible_now(satellites, observer, now):
    """Every satellite currently above the observer's horizon.

    Each entry carries the satellite's own lat/lon (for the map) and its
    elevation / azimuth / range as seen by the observer (for the sky view).
    """
    visible = []
    for sat in satellites:
        try:
            geocentric = sat.at(now)
            alt, az, distance = (geocentric - observer.at(now)).altaz()
        except Exception:
            continue

        # Skyfield yields NaN, not an exception, when SGP4 fails (e.g. decayed object).
        if math.isnan(alt.degrees) or alt.degrees <= 0:
            continue

        sub = geocentric.subpoint()
        visible.append(
            {
                "name": sat.name,
                "lat": round(float(sub.latitude.degrees), 4),
                "lon": round(float(sub.longitude.degrees), 4),
                "altitude_deg": round(float(alt.degrees), 2),
                "azimuth_deg": round(float(az.degrees), 2),
                "distance_km": round(float(distance.km), 1),
            }
        )

    visible.sort(key=lambda s: s["altitude_deg"], reverse=True)
    return visible


def compute_passes(satellites, observer, t0, hours=PASS_HOURS_AHEAD,
                   min_elevation=MIN_PASS_ELEVATION_DEG):
    """Complete (rise -> peak -> set) passes for the given satellites, soonest first.

    A pass already in progress at `t0` is skipped, because its rise time is in the past.
    """
    t1 = ts.from_datetime(t0.utc_datetime() + timedelta(hours=hours))
    passes = []

    for sat in satellites:
        try:
            times, events = sat.find_events(observer, t0, t1, altitude_degrees=min_elevation)
        except Exception:
            continue

        current = {}
        for t, event in zip(times, events):
            if event == 0:  # rise
                alt, az, _ = (sat - observer).at(t).altaz()
                current = {
                    "name": sat.name,
                    "rise_time_utc": t.utc_iso(),
                    "rise_azimuth_deg": round(float(az.degrees), 1),
                }
            elif event == 1 and current:  # culmination
                alt, az, _ = (sat - observer).at(t).altaz()
                current["peak_time_utc"] = t.utc_iso()
                current["max_elevation_deg"] = round(float(alt.degrees), 1)
                current["peak_azimuth_deg"] = round(float(az.degrees), 1)
            elif event == 2 and current:  # set
                alt, az, _ = (sat - observer).at(t).altaz()
                current["set_time_utc"] = t.utc_iso()
                current["set_azimuth_deg"] = round(float(az.degrees), 1)
                if "peak_time_utc" in current:
                    passes.append(current)
                current = {}

    passes.sort(key=lambda p: p["rise_time_utc"])
    return passes[:MAX_PASSES]


def compute_visibility(lat: float, lon: float, elevation_m: float = 0.0):
    """Returns (visible_now, next_passes) for an observer at (lat, lon).

    visible_now: all ~10k catalog satellites currently above the horizon.
    next_passes: upcoming passes of the PASS_WATCHLIST satellites over the next 24 h.
    """
    observer = _observer(lat, lon, elevation_m)
    now = ts.now()

    all_sats = list(catalog.get_satellites().values())
    visible_now = compute_visible_now(all_sats, observer, now)

    watchlist = catalog.match_prefixes(config.PASS_WATCHLIST)
    next_passes = compute_passes(watchlist, observer, now)

    return visible_now, next_passes


def compute_visibility_cached(lat: float, lon: float, elevation_m: float = 0.0):
    """compute_visibility with a short cache, so several browser tabs (or a fast
    refresh loop) don't each recompute the whole catalog.

    The key rounds the position to ~1 km, which doesn't change what is visible.
    """
    key = (round(lat, 2), round(lon, 2), round(elevation_m), tle_service.get_version())
    now = time.monotonic()

    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < config.VISIBILITY_CACHE_SECONDS:
            return hit[1]

    result = compute_visibility(lat, lon, elevation_m)

    with _cache_lock:
        _cache[key] = (now, result)
        if len(_cache) > 64:  # bound memory: drop the oldest entries
            for old in sorted(_cache, key=lambda k: _cache[k][0])[:32]:
                del _cache[old]
    return result
