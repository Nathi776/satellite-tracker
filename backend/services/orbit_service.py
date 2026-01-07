from sgp4.api import Satrec, jday
from datetime import datetime
import math

EARTH_RADIUS_KM = 6371.0

def get_satellite_position(tle):
    sat = Satrec.twoline2rv(tle["line1"], tle["line2"])

    now = datetime.utcnow()
    jd, fr = jday(
        now.year, now.month, now.day,
        now.hour, now.minute, now.second
    )

    e, r, v = sat.sgp4(jd, fr)

    if e != 0:
        print(f"SGP4 error {e} for {tle.get('name')}")
        return None

    x, y, z = r
    vx, vy, vz = v

    # Position → lat/lon
    lon = math.degrees(math.atan2(y, x))
    lat = math.degrees(math.atan2(z, math.sqrt(x*x + y*y)))

    # Altitude
    radius = math.sqrt(x*x + y*y + z*z)
    altitude_km = radius - EARTH_RADIUS_KM

    # Speed (km/s)
    speed_kms = math.sqrt(vx*vx + vy*vy + vz*vz)

    # Orbital period (minutes)
    try:
        mean_motion = float(tle["line2"][52:63])
        period_min = 1440 / mean_motion
    except:
        period_min = None

    return {
        "lat": lat,
        "lon": lon,
        "alt_km": altitude_km,
        "speed_kms": speed_kms,
        "period_min": period_min
    }
