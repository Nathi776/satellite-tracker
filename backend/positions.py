from skyfield.api import load, EarthSatellite, wgs84
from backend.satellites.african import AFRICAN_SATELLITES

# ISS_TLE data
ISS_TLE = (
    "1 25544U 98067A   25091.51782528  .00016717  00000+0  10270-3 0  9004",
    "2 25544  51.6405  90.2256 0004085  63.2012  53.5524 15.49776813443525"
)

def get_all_positions():
    ts = load.timescale()
    t = ts.now()

    satellites = []

    # ISS 
    iss = EarthSatellite(ISS_TLE[0], ISS_TLE[1], "ISS", ts)
    iss_geo = iss.at(t).subpoint()
    satellites.append({
        "name": "ISS",
        "latitude_deg": iss_geo.latitude.degrees,
        "longitude_deg": iss_geo.longitude.degrees,
        "alt_km": iss_geo.elevation.km
    })

    # African Satellites
    for name, data in AFRICAN_SATELLITES.items():
        tle = data["tle"]
        satellite = EarthSatellite(tle[0], tle[1], name, ts)
        geo = satellite.at(t).subpoint()
        satellites.append({
            "name": name,
            "country": data["country"],
            "latitude_deg": geo.latitude.degrees,
            "longitude_deg": geo.longitude.degrees,
            "alt_km": geo.elevation.km
        })

    return satellites