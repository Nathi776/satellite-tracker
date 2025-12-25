from skyfield.api import load, wgs84
from datetime import datetime, timedelta

def predict_passes():
    ts = load.timescale()
    t = ts.now()

    satellites = load.tle_file("https://celestrak.org/NORAD/elements/stations.txt")
    satellite = next(s for s in satellites if s.name == "ISS (ZARYA)")

    # Observer location (example: Johannesburg)
    observer = wgs84.latlon(-26.2041, 28.0473)

    results = []

    for minutes in range(0, 90, 5):
        t_future = ts.now() + timedelta(minutes=minutes)

        difference = satellite - observer
        topocentric = difference.at(t_future)

        alt, az, distance = topocentric.altaz()

        results.append({
            "time": t_future.utc_iso(),
            "altitude_deg": round(alt.degrees, 2),
            "azimuth_deg": round(az.degrees, 2),
            "distance_km": round(distance.km, 2)
        })

    return results
