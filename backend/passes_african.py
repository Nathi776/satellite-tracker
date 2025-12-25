from datetime import datetime, timedelta
from skyfield.api import load, wgs84, EarthSatellite, utc
import pytz

from backend.satellites.african import AFRICAN_SATELLITES

def predict_african_passes(
    satellite_name: str,
    hours_ahead: int = 24
):
    if satellite_name not in AFRICAN_SATELLITES:
        return {"error": "Satellite not found"}

    tle = AFRICAN_SATELLITES[satellite_name]["tle"]

    ts = load.timescale()
    eph = load("de421.bsp")
    satellite = EarthSatellite(tle[0], tle[1], satellite_name, ts)

    geo_position = wgs84.latlon(
        latitude_degrees=-25.7479,
        longitude_degrees=28.2293,
        elevation_m=1350
    )
    observer = eph["earth"] + geo_position

    start_time = ts.now()
    end_time = ts.from_datetime(
        (datetime.utcnow() + timedelta(hours=hours_ahead)).replace(tzinfo=utc)
    )

    times, events = satellite.find_events(
        geo_position,
        start_time,
        end_time,
        altitude_degrees=10.0
    )

    event_map = {0: "rise", 1: "culminate", 2: "set"}
    results = []
    current_pass = {}

    for t, event in zip(times, events):
        event_name = event_map[event]
        time_utc = t.utc_datetime().replace(tzinfo=pytz.UTC).isoformat()

        if event_name == "rise":
            current_pass = {"rise": time_utc}
        elif event_name == "culminate":
            astrometric = (satellite.at(t) - observer.at(t))
            elevation = astrometric.apparent().altaz()[0].degrees
            current_pass["max_elevation_deg"] = round(elevation, 2)
        elif event_name == "set":
            current_pass["set"] = time_utc
            results.append(current_pass)

    return {
        "satellite": satellite_name,
        "country": AFRICAN_SATELLITES[satellite_name]["country"],
        "city": "Pretoria",
        "passes": results
    }
