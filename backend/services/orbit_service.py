"""Current position and basic orbital facts for one satellite."""
import math

import numpy as np
from skyfield.api import EarthSatellite

from backend.services.satellites import ts


def get_satellite_position(sat: EarthSatellite, t=None):
    """Sub-satellite point, altitude, speed and period at time `t` (default: now).

    Latitude/longitude come from Skyfield's subpoint(), which rotates the inertial
    SGP4 position into the Earth-fixed frame and applies the WGS84 ellipsoid.
    (Taking atan2 of the raw SGP4 x/y/z gives an *inertial* longitude that drifts
    away from the real ground position as the Earth rotates.)

    Returns None if SGP4 cannot propagate this satellite (e.g. a decayed object).
    """
    if t is None:
        t = ts.now()

    try:
        geocentric = sat.at(t)
        sub = geocentric.subpoint()
        lat = float(sub.latitude.degrees)
        lon = float(sub.longitude.degrees)
        alt_km = float(sub.elevation.km)
        speed_kms = float(np.linalg.norm(geocentric.velocity.km_per_s))
    except Exception:
        return None

    # Skyfield returns NaN instead of raising for some SGP4 failures.
    if any(math.isnan(v) for v in (lat, lon, alt_km, speed_kms)):
        return None

    # no_kozai is the mean motion in radians per minute.
    no_kozai = getattr(sat.model, "no_kozai", 0.0)
    period_min = (2 * math.pi / no_kozai) if no_kozai > 0 else None

    return {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "alt_km": round(alt_km, 2),
        "speed_kms": round(speed_kms, 3),
        "period_min": round(period_min, 2) if period_min else None,
    }
