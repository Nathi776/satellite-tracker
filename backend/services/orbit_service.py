from sgp4.api import Satrec, jday
from datetime import datetime
import math

def get_satellite_position(tle):
    sat = Satrec.twoline2rv(tle["line1"], tle["line2"])

    now = datetime.utcnow()
    jd, fr = jday(
        now.year, now.month, now.day,
        now.hour, now.minute,
        now.second
    )

    e, r, v = sat.sgp4(jd, fr)

    if e != 0:
        return None

    x, y, z = r

    # Convert to lat/lon
    lon = math.degrees(math.atan2(y, x))
    lat = math.degrees(math.atan2(z, math.sqrt(x*x + y*y)))
    alt = math.sqrt(x*x + y*y + z*z) - 6371

    return {
        "lat": lat,
        "lon": lon,
        "alt_km": alt
    }
