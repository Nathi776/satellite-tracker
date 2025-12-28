from skyfield.api import EarthSatellite, load, wgs84
from datetime import datetime

def get_satellite_position(tle):
    ts = load.timescale()
    t = ts.now()

    satellite = EarthSatellite(
        tle["line1"],
        tle["line2"],
        tle["name"],
        ts
    )

    geocentric = satellite.at(t)
    subpoint = wgs84.subpoint(geocentric)

    return {
        "latitude": subpoint.latitude.degrees,
        "longitude": subpoint.longitude.degrees,
        "altitude_km": subpoint.elevation.km
    }
