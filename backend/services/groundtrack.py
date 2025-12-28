from skyfield.api import load, EarthSatellite, wgs84
from datetime import timedelta

def get_ground_track(tle, minutes=90, step=2):
    ts = load.timescale()
    now = ts.now()

    satellite = EarthSatellite(
        tle[0],
        tle[1],
        "SAT",
        ts
    )

    points = []

    for m in range(0, minutes, step):
        t = now + timedelta(minutes=m)
        geo = satellite.at(t).subpoint()

        points.append({
            "lat": geo.latitude.degrees,
            "lon": geo.longitude.degrees
        })

    return points
