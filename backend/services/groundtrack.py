"""Ground track: where the sub-satellite point travels over the next while."""
import math

import numpy as np
from skyfield.api import EarthSatellite

from backend.services.satellites import ts


def get_ground_track(sat: EarthSatellite, minutes: int = 90, step: float = 2, t0=None):
    """List of {"lat", "lon"} points, one every `step` minutes for `minutes` minutes.

    All times are evaluated in one vectorised Skyfield call. Points where SGP4
    fails (NaN) are dropped.
    """
    if t0 is None:
        t0 = ts.now()

    offsets_days = np.arange(0, minutes, step) / 1440.0
    times = ts.tt_jd(t0.tt + offsets_days)

    sub = sat.at(times).subpoint()
    lats = np.atleast_1d(sub.latitude.degrees)
    lons = np.atleast_1d(sub.longitude.degrees)

    return [
        {"lat": round(float(la), 4), "lon": round(float(lo), 4)}
        for la, lo in zip(lats, lons)
        if not (math.isnan(la) or math.isnan(lo))
    ]
