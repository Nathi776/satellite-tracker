"""A fast first pass: which satellites could be above an observer's horizon right now?

Working out each satellite's exact azimuth and elevation with Skyfield costs roughly 0.15 ms
per satellite, which adds up to about two seconds for the whole public catalogue, when only
around 5% of it is above any given horizon. This module runs SGP4 for all satellites at once
(sgp4's vectorised SatrecArray) and does the rotation to the ground in plain NumPy, which takes
a few tens of milliseconds. The exact calculation then only needs to run on the survivors.

The estimate ignores polar motion (metres) and uses the mean Earth rotation angle, so it can be
off by a few thousandths of a degree. Callers keep a margin below the horizon so that a satellite
that is truly above it is never dropped.
"""
import math
import threading

import numpy as np
from sgp4.api import SatrecArray

DEFAULT_MARGIN_DEG = 1.5

_lock = threading.Lock()
_cache = {"key": None, "array": None}


def _satrec_array(satellites):
    """SatrecArray for this satellite list, kept until the catalogue changes."""
    key = (len(satellites), id(satellites[0]), id(satellites[-1]))
    with _lock:
        if _cache["key"] != key:
            _cache["array"] = SatrecArray([s.model for s in satellites])
            _cache["key"] = key
        return _cache["array"]


def warm(satellites):
    """Build the SatrecArray ahead of time (the refresher calls this before a swap)."""
    _satrec_array(satellites)


def above_horizon_mask(satellites, observer, now, margin_deg=DEFAULT_MARGIN_DEG):
    """Boolean array: True where the satellite's elevation is above -margin_deg.

    `observer` is a Skyfield GeographicPosition and `now` a Skyfield Time. SGP4 failures
    (decayed objects, bad elements) come back False.
    """
    array = _satrec_array(satellites)
    jd = np.array([now.whole])
    fraction = np.array([now.tai_fraction - now._leap_seconds() / 86400.0])
    error, position, _velocity = array.sgp4(jd, fraction)
    r_teme = position[:, 0, :]  # (n, 3) km

    # TEME -> Earth-fixed: rotate by the Greenwich mean sidereal angle
    theta = math.radians(float(now.gmst) * 15.0)
    c, s = math.cos(theta), math.sin(theta)
    x = r_teme[:, 0] * c + r_teme[:, 1] * s
    y = -r_teme[:, 0] * s + r_teme[:, 1] * c
    r_itrs = np.stack([x, y, r_teme[:, 2]], axis=1)

    lat = observer.latitude.radians
    lon = observer.longitude.radians
    up = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
    observer_km = np.asarray(observer.itrs_xyz.km, dtype=float)

    d = r_itrs - observer_km
    distance = np.linalg.norm(d, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sin_el = (d @ up) / distance
    ok = (error[:, 0] == 0) & np.isfinite(sin_el)
    return ok & (sin_el > math.sin(math.radians(-margin_deg)))
