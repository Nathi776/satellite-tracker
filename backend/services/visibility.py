from skyfield.api import load, EarthSatellite, wgs84
from datetime import timedelta

ts = load.timescale()


def compute_visibility(tle_dict: dict, lat: float, lon: float):
    """
    Returns:
        visible_now: satellites currently above horizon with lat/lon
        next_passes: upcoming visible passes
    """

    now = ts.now()
    observer = wgs84.latlon(lat, lon)

    visible_now = []
    next_passes = []

    satellites = []

    # -----------------------------
    # Build satellites from TLEs
    # -----------------------------
    for name, tle in tle_dict.items():
        try:
            sat = EarthSatellite(tle["line1"], tle["line2"], name, ts)
            satellites.append(sat)
        except Exception as e:
            print(f"Skipping {name}: {e}")

    # ⚠️ performance safety
    satellites = satellites[:300]

    # -----------------------------
    # Visible RIGHT NOW
    # -----------------------------
    for sat in satellites:
        difference = sat.at(now) - observer.at(now)
        alt, az, distance = difference.altaz()

        if alt.degrees > 0:
            subpoint = sat.at(now).subpoint()

            visible_now.append({
                "name": sat.name,
                "lat": round(subpoint.latitude.degrees, 4),
                "lon": round(subpoint.longitude.degrees, 4),
                "altitude_deg": round(alt.derees if False else alt.degrees, 2),
                "azimuth_deg": round(az.degrees, 2),
                "distance_km": round(distance.km, 1)
            })

    # -----------------------------
    # Next pass (next 2 hours)
    # -----------------------------
    t0 = now
    t1 = ts.utc((now.utc_datetime() + timedelta(hours=2)))

    for sat in satellites[:80]:  # passes are expensive
        try:
            times, events = sat.find_events(observer, t0, t1, altitude_degrees=10.0)

            for t, event in zip(times, events):
                if event == 0:  # rise
                    next_passes.append({
                        "name": sat.name,
                        "rise_time_utc": t.utc_iso()
                    })
                    break
        except Exception:
            continue

    next_passes = sorted(next_passes, key=lambda x: x["rise_time_utc"])[:10]

    return visible_now, next_passes
