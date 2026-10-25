import math

from skyfield.api import wgs84

from backend.services import satellites as catalog
from backend.services.groundtrack import get_ground_track
from backend.services.orbit_service import get_satellite_position
from backend.services.satellites import ts
from backend.services.visibility import _observer, compute_visible_now


def iss():
    return catalog.find_satellite("ISS")


def test_iss_position_is_physically_plausible():
    pos = get_satellite_position(iss(), ts.utc(2025, 12, 26, 12))
    assert abs(pos["lat"]) <= 51.7          # can't exceed the orbital inclination
    assert -180 <= pos["lon"] <= 180
    assert 380 < pos["alt_km"] < 450
    assert 7.5 < pos["speed_kms"] < 7.8
    assert 90 < pos["period_min"] < 94


def test_position_matches_skyfield_subpoint():
    """The API's lat/lon must equal Skyfield's WGS84 sub-satellite point."""
    t = ts.utc(2025, 12, 26, 12)
    pos = get_satellite_position(iss(), t)
    sub = wgs84.subpoint(iss().at(t))
    assert math.isclose(pos["lat"], sub.latitude.degrees, abs_tol=1e-3)
    assert math.isclose(pos["lon"], sub.longitude.degrees, abs_tol=1e-3)


def test_old_inertial_longitude_was_wrong():
    """Regression: atan2 on raw SGP4 (inertial) x/y ignores Earth's rotation and drifts
    away from the true ground longitude."""
    sat = iss()
    t = ts.utc(2025, 12, 26, 18)
    e, r, v = sat.model.sgp4(t.whole, t.tai_fraction - t._leap_seconds() / 86400.0)
    inertial_lon = math.degrees(math.atan2(r[1], r[0]))
    true_lon = get_satellite_position(sat, t)["lon"]
    diff = abs((inertial_lon - true_lon + 180) % 360 - 180)
    assert diff > 1.0  # the old formula is off by at least a degree here


def test_ground_track_shape_and_continuity():
    track = get_ground_track(iss(), minutes=90, step=2, t0=ts.utc(2025, 12, 26, 12))
    assert len(track) == 45
    assert all(abs(p["lat"]) <= 51.7 for p in track)
    # a 2-minute step is ~15 degrees of orbit at most, so no jumps except the 360 wrap
    for a, b in zip(track, track[1:]):
        dlon = abs((b["lon"] - a["lon"] + 180) % 360 - 180)
        assert dlon < 30


def test_visible_now_entries_have_everything_the_frontend_needs():
    t = ts.utc(2025, 12, 26, 12)
    sats = list(catalog.get_satellites().values())
    # an observer directly under the ISS must see it near the zenith
    pos = get_satellite_position(iss(), t)
    observer = _observer(pos["lat"], pos["lon"])
    visible = compute_visible_now(sats, observer, t)
    entry = next(v for v in visible if v["name"] == "ISS (ZARYA)")
    assert set(entry) == {"name", "lat", "lon", "altitude_deg", "azimuth_deg", "distance_km"}
    assert entry["altitude_deg"] > 85
    assert 380 < entry["distance_km"] < 450
    # sorted highest first
    alts = [v["altitude_deg"] for v in visible]
    assert alts == sorted(alts, reverse=True)
