import requests
from datetime import datetime

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"

_cached_tles = {
    "last_updated": None,
    "data": {}
}

def fetch_tles():
    global _cached_tles

    print("Fetching TLEs from CelesTrak (GP API)...")

    response = requests.get(CELESTRAK_URL, timeout=10)
    response.raise_for_status()

    lines = response.text.strip().splitlines()

    tle_data = {}
    i = 0

    while i < len(lines) - 2:
        name = lines[i].strip()
        line1 = lines[i + 1].strip()
        line2 = lines[i + 2].strip()

        if line1.startswith("1 ") and line2.startswith("2 "):
            tle_data[name] = {
                "name": name,
                "line1": line1,
                "line2": line2
            }

        i += 3

    _cached_tles = {
        "last_updated": datetime.utcnow(),
        "data": tle_data
    }

    print(f"Loaded {len(tle_data)} satellites from CelesTrak")
    return tle_data


def get_tles():
    if _cached_tles["last_updated"] is None:
        fetch_tles()
    return _cached_tles["data"]
