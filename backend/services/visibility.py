"""What an observer can see: satellites above the horizon now, and upcoming passes.

"Above the horizon" is geometry. "Visible" additionally needs a dark sky, a satellite
in sunlight, and enough brightness. See services/sky.py and config.py.
"""
import math
import threading
import time
from datetime import timedelta

import numpy as np
from skyfield.api import wgs84

from backend import config
from backend.services import satellites as catalog
from backend.services import prefilter, sky, tle_service
from backend.services.magnetic import declination_deg
from backend.services.satellites import ts

MIN_PASS_ELEVATION_DEG = 10.0
MIN_NAKED_EYE_ELEVATION_DEG = 10.0
PASS_HOURS_AHEAD = 24
MAX_PASS_HOURS = 72
MAX_PASSES = 20
PASS_SAMPLE_SECONDS = 10

_cache_lock = threading.Lock()
_cache = {}  # key -> (computed_at_monotonic, result)


def _observer(lat, lon, elevation_m=0.0):
    return wgs84.latlon(lat, lon, elevation_m=elevation_m)


def _wrap180(delta):
    """Smallest signed angle difference, so a step from 359 deg to 1 deg is +2, not -358."""
    return (delta + 180.0) % 360.0 - 180.0


def _visibility_status(dark: bool, lit: bool, naked_eye: bool) -> str:
    if naked_eye:
        return "visible"      # dark sky, in sunlight, bright enough
    if not dark:
        return "daylight"     # sky too bright to see it
    if not lit:
        return "in_shadow"    # in Earth's shadow: dark sky but nothing to see
    return "faint"            # sunlit on a dark sky, but too faint / too low / brightness unknown


# ---------------------------------------------------------------------------
# Right now
# ---------------------------------------------------------------------------
# Below this many satellites the exact calculation is quick enough on its own.
PREFILTER_MIN_SATELLITES = 500


def compute_visible_now(satellites, observer, now, sun_alt=None, include_below_horizon=False,
                        prefilter_min=PREFILTER_MIN_SATELLITES):
    """Every satellite currently above the observer's horizon.

    Each entry carries the satellite's own lat/lon (for the map), what the observer
    sees (elevation / azimuth / range), whether it is sunlit and how bright it should
    be, and per-second rates so a client can move it smoothly between refreshes.
    """
    if sun_alt is None:
        sun_alt = float(sky.sun_altitude_deg(observer, now))
    dark = bool(sky.is_dark_enough(sun_alt))

    # For a big catalogue, first find the few percent that can be above the horizon
    # (vectorised, tens of ms) and only run the exact calculation on those.
    if not include_below_horizon and len(satellites) >= prefilter_min:
        mask = prefilter.above_horizon_mask(satellites, observer, now)
        satellites = [sat for sat, keep in zip(satellites, mask) if keep]

    later = ts.tt_jd(now.tt + 1.0 / 86400.0)  # one second ahead, for the rates
    observer_now = observer.at(now)
    observer_later = observer.at(later)

    visible = []
    for sat in satellites:
        try:
            geocentric = sat.at(now)
            alt, az, distance = (geocentric - observer_now).altaz()
        except Exception:
            continue

        # Skyfield yields NaN, not an exception, when SGP4 fails (e.g. decayed object).
        if math.isnan(alt.degrees) or (alt.degrees <= 0 and not include_below_horizon):
            continue

        sub = geocentric.subpoint()
        geocentric_later = sat.at(later)
        alt2, az2, _ = (geocentric_later - observer_later).altaz()
        sub2 = geocentric_later.subpoint()

        lit = bool(sky.is_sunlit_geocentric(geocentric, now))

        magnitude = None
        std_mag, mag_source = sky.standard_magnitude_info(sat.name, sat.model.satnum)
        if std_mag is not None:
            phase = float(sky.phase_angle_rad(sat, observer, now))
            magnitude = float(sky.estimate_magnitude(std_mag, distance.km, phase))

        naked_eye = bool(
            dark
            and lit
            and alt.degrees >= MIN_NAKED_EYE_ELEVATION_DEG
            and sky.is_bright_enough(magnitude, mag_source)
        )

        visible.append(
            {
                "name": sat.name,
                "lat": round(float(sub.latitude.degrees), 4),
                "lon": round(float(sub.longitude.degrees), 4),
                "altitude_deg": round(float(alt.degrees), 2),
                "above_horizon": bool(alt.degrees > 0),
                "azimuth_deg": round(float(az.degrees), 2),
                "distance_km": round(float(distance.km), 1),
                "sunlit": lit,
                "magnitude": round(magnitude, 1) if magnitude is not None else None,
                # where the figure comes from: manual | quicksat | size (rough) | None
                "magnitude_source": mag_source if magnitude is not None else None,
                "naked_eye": naked_eye,
                "status": _visibility_status(dark, lit, naked_eye),
                # degrees per second, for client-side extrapolation between refreshes
                "altitude_rate": round(float(alt2.degrees - alt.degrees), 4),
                "azimuth_rate": round(float(_wrap180(az2.degrees - az.degrees)), 4),
                "lat_rate": round(float(sub2.latitude.degrees - sub.latitude.degrees), 5),
                "lon_rate": round(float(_wrap180(sub2.longitude.degrees - sub.longitude.degrees)), 5),
            }
        )

    visible.sort(key=lambda s: s["altitude_deg"], reverse=True)
    return visible


# ---------------------------------------------------------------------------
# Passes
# ---------------------------------------------------------------------------
def _classify_pass(sat, observer, rise_t, peak_t, set_t, min_elevation):
    """How well can this pass actually be seen? Samples it every PASS_SAMPLE_SECONDS."""
    duration_s = (set_t.tt - rise_t.tt) * 86400.0
    n = max(3, int(duration_s / PASS_SAMPLE_SECONDS) + 1)
    times = ts.linspace(rise_t, set_t, n)

    alt, _, distance = (sat - observer).at(times).altaz()
    alt_deg = np.atleast_1d(alt.degrees)
    sun_alt = np.atleast_1d(sky.sun_altitude_deg(observer, times))
    lit = np.atleast_1d(sky.is_sunlit(sat, times))
    dark = np.atleast_1d(sky.is_dark_enough(sun_alt))

    std_mag, mag_source = sky.standard_magnitude_info(sat.name, sat.model.satnum)
    magnitude = None
    bright = np.zeros(n, dtype=bool)
    if std_mag is not None:
        phase = np.atleast_1d(sky.phase_angle_rad(sat, observer, times))
        magnitude = np.atleast_1d(sky.estimate_magnitude(std_mag, np.atleast_1d(distance.km), phase))
        bright = np.atleast_1d(sky.is_bright_enough(magnitude, mag_source))

    seen = dark & lit & bright & (alt_deg >= max(min_elevation, MIN_NAKED_EYE_ELEVATION_DEG))

    if seen.any():
        status = "visible"
    elif (dark & lit).any():
        status = "faint"
    elif dark.any():
        status = "in_shadow"
    else:
        status = "daylight"

    info = {
        "visibility": status,
        "duration_seconds": int(round(duration_s)),
        "sun_altitude_deg": round(float(sun_alt[n // 2]), 1),
        "sunlit_at_peak": bool(sky.is_sunlit(sat, peak_t)),
        "visible_from_utc": None,
        "visible_until_utc": None,
        "visible_seconds": 0,
        "magnitude": None,
        "magnitude_source": None,
    }
    if seen.any():
        idx = np.flatnonzero(seen)
        info["visible_from_utc"] = times[int(idx[0])].utc_iso()
        info["visible_until_utc"] = times[int(idx[-1])].utc_iso()
        info["visible_seconds"] = int(round(seen.sum() * duration_s / max(n - 1, 1)))
    if magnitude is not None:
        pool = magnitude[seen] if seen.any() else magnitude[dark & lit] if (dark & lit).any() else magnitude
        info["magnitude"] = round(float(pool.min()), 1)  # brightest moment of the pass
        info["magnitude_source"] = mag_source
    return info


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

        rise = peak = None
        entry = {}
        for t, event in zip(times, events):
            alt, az, _ = (sat - observer).at(t).altaz()
            if event == 0:  # rise
                rise, peak, entry = t, None, {
                    "name": sat.name,
                    "rise_time_utc": t.utc_iso(),
                    "rise_azimuth_deg": round(float(az.degrees), 1),
                    "rise_direction": sky.compass_point(float(az.degrees)),
                }
            elif event == 1 and rise is not None:  # culmination
                peak = t
                entry.update(
                    peak_time_utc=t.utc_iso(),
                    max_elevation_deg=round(float(alt.degrees), 1),
                    peak_azimuth_deg=round(float(az.degrees), 1),
                    peak_direction=sky.compass_point(float(az.degrees)),
                )
            elif event == 2 and rise is not None and peak is not None:  # set
                entry.update(
                    set_time_utc=t.utc_iso(),
                    set_azimuth_deg=round(float(az.degrees), 1),
                    set_direction=sky.compass_point(float(az.degrees)),
                )
                entry.update(_classify_pass(sat, observer, rise, peak, t, min_elevation))
                passes.append(entry)
                rise, peak, entry = None, None, {}

    passes.sort(key=lambda p: p["rise_time_utc"])
    return passes[:MAX_PASSES]


# ---------------------------------------------------------------------------
# Everything for one observer
# ---------------------------------------------------------------------------
def _declination(lat: float, lon: float):
    """Magnetic declination at the observer, or None if the model is unavailable."""
    try:
        return round(declination_deg(lat, lon), 1)
    except Exception:
        return None


def compute_passes_over(satellites, lat: float, lon: float, hours: int = PASS_HOURS_AHEAD,
                        elevation_m: float = 0.0):
    """Passes of the given satellites over a ground location (see compute_passes)."""
    return compute_passes(satellites, _observer(lat, lon, elevation_m), ts.now(), hours=hours)


def compute_visibility(lat: float, lon: float, elevation_m: float = 0.0,
                       hours: int = PASS_HOURS_AHEAD):
    """Observer sky state, every satellite above the horizon, and upcoming watchlist passes."""
    observer = _observer(lat, lon, elevation_m)
    now = ts.now()
    sun_alt = float(sky.sun_altitude_deg(observer, now))

    all_sats = list(catalog.get_satellites().values())
    visible_now = compute_visible_now(all_sats, observer, now, sun_alt)

    watchlist = catalog.match_prefixes(config.PASS_WATCHLIST)
    next_passes = compute_passes(watchlist, observer, now, hours=hours)

    return {
        "generated_at": now.utc_iso(),
        "observer": {
            "lat": lat,
            "lon": lon,
            "sun_altitude_deg": round(sun_alt, 1),
            "sky": sky.sky_state(sun_alt),
            "dark_enough": bool(sky.is_dark_enough(sun_alt)),
            "declination_deg": _declination(lat, lon),
        },
        "visible_now": visible_now,
        "next_passes": next_passes,
    }


def compute_satellite_view(sat, lat: float, lon: float, hours: int = PASS_HOURS_AHEAD,
                           elevation_m: float = 0.0):
    """Where to look for one satellite, right now, plus its next pass.

    Unlike `visible_now` this also answers for a satellite below the horizon (negative
    elevation). Returns None if the orbit cannot be propagated.
    """
    observer = _observer(lat, lon, elevation_m)
    now = ts.now()
    sun_alt = float(sky.sun_altitude_deg(observer, now))
    rows = compute_visible_now([sat], observer, now, sun_alt, include_below_horizon=True)
    if not rows:
        return None
    look = rows[0]
    look["direction"] = sky.compass_point(look["azimuth_deg"])

    passes = compute_passes([sat], observer, now, hours=hours)
    return {
        "generated_at": now.utc_iso(),
        "look": look,
        "next_pass": passes[0] if passes else None,
        "passes": passes[:5],
        "sky": sky.sky_state(sun_alt),
    }


def compute_visibility_cached(lat: float, lon: float, elevation_m: float = 0.0,
                              hours: int = PASS_HOURS_AHEAD):
    """compute_visibility with a short cache, so several browser tabs (or a fast
    refresh loop) don't each recompute the whole catalog.

    Returns (result, age_seconds): how old the result is, so that a client can bring it
    up to date without trusting its own clock. Treat the result as read-only.

    The key rounds the position to ~1 km, which doesn't change what is visible.
    """
    # Load (or refresh) the catalog first: that can change the data version, and the
    # key must use the version the result will actually be computed from.
    catalog.get_satellites()
    key = (round(lat, 2), round(lon, 2), round(elevation_m), hours, catalog.get_version())
    now = time.monotonic()

    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < config.VISIBILITY_CACHE_SECONDS:
            return hit[1], now - hit[0]

    computed_at = time.monotonic()
    result = compute_visibility(lat, lon, elevation_m, hours)

    with _cache_lock:
        _cache[key] = (computed_at, result)
        if len(_cache) > 64:  # bound memory: drop the oldest entries
            for old in sorted(_cache, key=lambda k: _cache[k][0])[:32]:
                del _cache[old]
    return result, time.monotonic() - computed_at
