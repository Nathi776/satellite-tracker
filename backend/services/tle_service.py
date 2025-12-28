import requests

TLE_URL = "https://celestrak.org/NORAD/elements/active.txt"

def get_tle_by_name(name: str):
    response = requests.get(TLE_URL)
    lines = response.text.splitlines()

    for i in range(0, len(lines), 3):
        if name.lower() in lines[i].lower():
            return {
                "name": lines[i],
                "line1": lines[i + 1],
                "line2": lines[i + 2]
            }

    return None
