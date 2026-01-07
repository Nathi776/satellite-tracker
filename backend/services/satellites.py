# backend/services/satellites.py
from skyfield.api import EarthSatellite, load

ts = load.timescale()

def build_satellites(tle_dict):
    satellites = []
    for name, tle in tle_dict.items():
        try:
            sat = EarthSatellite(tle["line1"], tle["line2"], name, ts)
            satellites.append(sat)
        except Exception as e:
            print(f"Skipping {name}: {e}")
    return satellites
