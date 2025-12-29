import requests
from datetime import datetime

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/active.txt"

_cached_tles = {
    "last_updated": None,
    "data": {}
}

def fetch_tles():
    global _cached_tles

    print("Fetching TLEs from CelesTrak...")

    response = requests.get(CELESTRAK_URL)
    lines = response.text.splitlines()

    tle_data = {}
    i = 0

    while i < len(lines):
        if lines[i].strip() and i + 2 < len(lines):
            name = lines[i].strip()
            line1 = lines[i + 1]
            line2 = lines[i + 2]

            tle_data[name] = {
                "line1": line1,
                "line2": line2
            }
            i += 3
        else:
            i += 1

    _cached_tles = {
        "last_updated": datetime.utcnow(),
        "data": tle_data
    }

    print(f"Loaded {len(tle_data)} satellites")

    return tle_data


def get_tles():
    # Refresh every 6 hours
    if (
        _cached_tles["last_updated"] is None
        or (datetime.utcnow() - _cached_tles["last_updated"]).seconds > 21600
    ):
        return fetch_tles()

    return _cached_tles["data"]
