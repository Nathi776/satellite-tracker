"""Sun, darkness, sunlight and brightness: what decides whether a satellite can be seen.

Everything here is vectorised, so it accepts a single Skyfield time or an array of times.
"""
import re
import threading

import numpy as np
from skyfield.api import Loader

from backend import config
from backend.services import quicksat

# de421.bsp lives in the repo root (Skyfield downloads it there if it is missing).
_loader = Loader(str(config.BASE_DIR.parent), verbose=False)
_eph = None
_eph_lock = threading.Lock()


def get_ephemeris():
    """Load the planetary ephemeris once, on first use."""
    global _eph
    with _eph_lock:
        if _eph is None:
            _eph = _loader("de421.bsp")
        return _eph


# ---------------------------------------------------------------------------
# The Sun and the observer's sky
# ---------------------------------------------------------------------------
def sun_altitude_deg(observer, t):
    """Altitude of the Sun above the observer's horizon, in degrees."""
    eph = get_ephemeris()
    apparent = (eph["earth"] + observer).at(t).observe(eph["sun"]).apparent()
    alt, _, _ = apparent.altaz()
    return alt.degrees


def sky_state(sun_alt: float) -> str:
    """'day' | 'twilight_civil' | 'twilight_nautical' | 'twilight_astronomical' | 'night'."""
    if sun_alt >= 0:
        return "day"
    if sun_alt >= -6:
        return "twilight_civil"
    if sun_alt >= -12:
        return "twilight_nautical"
    if sun_alt >= -18:
        return "twilight_astronomical"
    return "night"


def is_dark_enough(sun_alt):
    """True where the sky is dark enough to see bright satellites."""
    return np.asarray(sun_alt) < config.DARK_SKY_SUN_ALTITUDE_DEG


# ---------------------------------------------------------------------------
# Satellite illumination
# ---------------------------------------------------------------------------
def is_sunlit(satellite, t):
    """True where the satellite is in sunlight (not in Earth's shadow)."""
    return np.asarray(satellite.at(t).is_sunlit(get_ephemeris()))


def phase_angle_rad(satellite, observer, t):
    """Sun-satellite-observer angle in radians (0 = full, pi = new)."""
    eph = get_ephemeris()
    sat_pos = satellite.at(t).position.km
    obs_pos = observer.at(t).position.km
    sun_pos = eph["earth"].at(t).observe(eph["sun"]).position.km

    to_obs = obs_pos - sat_pos
    to_sun = sun_pos - sat_pos
    cos_phi = (to_obs * to_sun).sum(axis=0) / (
        np.linalg.norm(to_obs, axis=0) * np.linalg.norm(to_sun, axis=0)
    )
    return np.arccos(np.clip(cos_phi, -1.0, 1.0))


# ---------------------------------------------------------------------------
# Brightness
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def standard_magnitude(name: str, norad: int | None = None):
    """Standard magnitude for a known object, or None if we have no figure.

    Hand-entered figures (matched by name) win; otherwise McCants' quicksat.mag is
    consulted by NORAD number."""
    wanted = _normalize(name)
    for known, mag in config.BRIGHT_STD_MAGS.items():
        if _normalize(known) == wanted:
            return mag
    return quicksat.standard_magnitude(norad)


def estimate_magnitude(std_mag, range_km, phase_rad):
    """Apparent magnitude of a diffusely reflecting sphere (the model used for the
    standard-magnitude figures published by McCants / Heavens-Above)."""
    phase_rad = np.asarray(phase_rad, dtype=float)
    phase_term = np.sin(phase_rad) + (np.pi - phase_rad) * np.cos(phase_rad)
    phase_term = np.clip(phase_term, 1e-3, None)  # avoid log(0) at a thin crescent
    return std_mag - 15.0 + 5.0 * np.log10(np.asarray(range_km, dtype=float)) - 2.5 * np.log10(phase_term)


def is_bright_enough(magnitude):
    """magnitude may be None (unknown brightness) or an array."""
    if magnitude is None:
        return False
    return np.asarray(magnitude) <= config.NAKED_EYE_LIMIT_MAG


# ---------------------------------------------------------------------------
# Directions
# ---------------------------------------------------------------------------
_POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass_point(azimuth_deg: float) -> str:
    """0 -> 'N', 90 -> 'E', 225 -> 'SW' ..."""
    return _POINTS[int(((azimuth_deg % 360) + 11.25) // 22.5) % 16]
