from skyfield.api import load, EarthSatellite
import requests

from datetime import datetime, timezone

TLE_URL = "https://celestrak.org/NORAD/elements/stations.txt"

def get_iss():
    response = requests.get(TLE_URL)
    lines = response.text.splitlines()

    for i in range(len(lines)):
        if "ISS (ZARYA)" in lines[i]:
            name = lines[i]
            line1 = lines[i + 1]
            line2 = lines[i + 2]
            return EarthSatellite(line1, line2, name)
        
    return None

def get_iss_position():
    ts = load.timescale()
    t = ts.now()

    iss = get_iss()
    geocentric = iss.at(t)
    subpoint = geocentric.subpoint()

    return {
        "latitude": subpoint.latitude.degrees,
        "longitude": subpoint.longitude.degrees,
        "altitude_km": subpoint.elevation.km
    }