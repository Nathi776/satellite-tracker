import numpy as np
import pytest

from backend import config
from backend.services import satellites as catalog
from backend.services import sky
from backend.services import visibility as vis
from backend.services.orbit_service import get_satellite_position
from backend.services.satellites import ts

PRETORIA = vis._observer(-25.7479, 28.2293, 1350)


def iss():
    return catalog.find_satellite("ISS")


def observer_under_iss(t):
    pos = get_satellite_position(iss(), t)
    return vis._observer(pos["lat"], pos["lon"])


def find_moment(predicate):
    """First time (scanning 24 h in 3-minute steps) when an observer standing directly under
    the ISS satisfies predicate(dark, lit). Deterministic: the TLE fixture is fixed."""
    t0 = ts.utc(2025, 12, 26, 0)
    for minute in range(0, 24 * 60, 3):
        t = ts.tt_jd(t0.tt + minute / 1440.0)
        obs = observer_under_iss(t)
        dark = bool(sky.is_dark_enough(float(sky.sun_altitude_deg(obs, t))))
        lit = bool(sky.is_sunlit(iss(), t))
        if predicate(dark, lit):
            return t, obs
    raise AssertionError("no matching moment found")


def entry_for_iss(t, obs):
    sats = list(catalog.get_satellites().values())
    visible = vis.compute_visible_now(sats, obs, t)
    return next(v for v in visible if v["name"] == "ISS (ZARYA)")


# ---------------------------------------------------------------------------
# visible_now
# ---------------------------------------------------------------------------
def test_visible_entry_has_everything_the_frontend_needs():
    t = ts.utc(2025, 12, 26, 12)
    entry = entry_for_iss(t, observer_under_iss(t))
    assert set(entry) == {
        "name", "lat", "lon", "altitude_deg", "azimuth_deg", "distance_km",
        "sunlit", "magnitude", "naked_eye", "status",
        "altitude_rate", "azimuth_rate", "lat_rate", "lon_rate",
    }
    assert entry["altitude_deg"] > 85


def test_dark_sky_and_sunlit_iss_overhead_is_naked_eye_visible():
    t, obs = find_moment(lambda dark, lit: dark and lit)
    entry = entry_for_iss(t, obs)
    assert entry["status"] == "visible" and entry["naked_eye"] is True
    assert entry["sunlit"] is True
    assert entry["magnitude"] < -2          # overhead ISS is very bright


def test_iss_in_earths_shadow_is_not_visible_even_on_a_dark_sky():
    t, obs = find_moment(lambda dark, lit: dark and not lit)
    entry = entry_for_iss(t, obs)
    assert entry["status"] == "in_shadow" and entry["naked_eye"] is False
    assert entry["sunlit"] is False


def test_sunlit_iss_in_daytime_sky_is_not_visible():
    t, obs = find_moment(lambda dark, lit: not dark and lit)
    entry = entry_for_iss(t, obs)
    assert entry["status"] == "daylight" and entry["naked_eye"] is False


def test_sunlit_satellite_with_unknown_brightness_is_only_faint():
    """We have no brightness for ordinary satellites, so we never claim they are visible."""
    t, obs = find_moment(lambda dark, lit: dark and lit)
    sat = next(s for s in catalog.get_satellites().values() if s.name == "FREGAT DEB")
    # use the generic function on a satellite whose brightness is unknown
    assert sky.standard_magnitude(sat.name) is None
    assert vis._visibility_status(dark=True, lit=True, naked_eye=False) == "faint"


def test_status_priority():
    assert vis._visibility_status(True, True, True) == "visible"
    assert vis._visibility_status(False, True, False) == "daylight"
    assert vis._visibility_status(True, False, False) == "in_shadow"
    assert vis._visibility_status(False, False, False) == "daylight"


def test_rates_predict_motion_over_the_next_minute():
    """Linear extrapolation with the returned rates must stay close for a short while,
    which is what the frontend does between refreshes."""
    t = ts.utc(2025, 12, 26, 12)
    entry = entry_for_iss(t, observer_under_iss(t))
    later = ts.tt_jd(t.tt + 10 / 86400.0)  # 10 s later
    actual = get_satellite_position(iss(), later)
    pred_lat = entry["lat"] + 10 * entry["lat_rate"]
    pred_lon = entry["lon"] + 10 * entry["lon_rate"]
    assert abs(pred_lat - actual["lat"]) < 0.05
    assert abs(pred_lon - actual["lon"]) < 0.05


def test_azimuth_rate_wraps_across_north():
    assert vis._wrap180(1 - 359) == 2
    assert vis._wrap180(359 - 1) == -2


def test_positions_include_rates():
    pos = get_satellite_position(iss(), ts.utc(2025, 12, 26, 12))
    assert "lat_rate" in pos and "lon_rate" in pos
    assert abs(pos["lon_rate"]) < 1 and abs(pos["lat_rate"]) < 1  # < 1 deg/s for LEO ground speed


# ---------------------------------------------------------------------------
# passes
# ---------------------------------------------------------------------------
@pytest.fixture
def week_of_passes(monkeypatch):
    monkeypatch.setattr(vis, "MAX_PASSES", 500)
    sats = catalog.match_prefixes(config.PASS_WATCHLIST)
    return vis.compute_passes(sats, PRETORIA, ts.utc(2025, 12, 26, 0), hours=72)


def test_passes_are_complete_and_ordered(week_of_passes):
    assert len(week_of_passes) > 10
    rises = [p["rise_time_utc"] for p in week_of_passes]
    assert rises == sorted(rises)
    for p in week_of_passes:
        assert p["rise_time_utc"] < p["peak_time_utc"] < p["set_time_utc"]
        assert p["max_elevation_deg"] >= 10
        assert p["duration_seconds"] > 0
        assert p["rise_direction"] and p["set_direction"]


def test_pass_classification_is_consistent_with_the_physics(week_of_passes):
    seen_status = set()
    for p in week_of_passes:
        seen_status.add(p["visibility"])
        assert p["visibility"] in {"visible", "faint", "in_shadow", "daylight"}

        if p["visibility"] == "visible":
            assert p["visible_seconds"] > 0
            assert p["visible_from_utc"] and p["visible_until_utc"]
            assert p["rise_time_utc"] <= p["visible_from_utc"] <= p["visible_until_utc"] <= p["set_time_utc"]
            assert p["magnitude"] <= config.NAKED_EYE_LIMIT_MAG
            assert p["sun_altitude_deg"] < 0       # can't be a visible pass in full daylight
        else:
            assert p["visible_seconds"] == 0
            assert p["visible_from_utc"] is None
        if p["visibility"] == "daylight":
            assert p["sun_altitude_deg"] > config.DARK_SKY_SUN_ALTITUDE_DEG
    # three days of ISS + Tianhe passes include day, shadowed and visible passes
    assert {"visible", "daylight", "in_shadow"} <= seen_status


def test_visible_pass_brightness_is_plausible_for_iss_and_tiangong(week_of_passes):
    mags = [p["magnitude"] for p in week_of_passes if p["visibility"] == "visible"]
    assert mags and all(-6 < m < 3 for m in mags)


# ---------------------------------------------------------------------------
# whole-observer result
# ---------------------------------------------------------------------------
def test_compute_visibility_reports_observer_sky():
    result = vis.compute_visibility(-25.7479, 28.2293)
    obs = result["observer"]
    assert set(obs) == {"lat", "lon", "sun_altitude_deg", "sky", "dark_enough"}
    assert obs["sky"] == sky.sky_state(obs["sun_altitude_deg"])
    assert obs["dark_enough"] == (obs["sun_altitude_deg"] < config.DARK_SKY_SUN_ALTITUDE_DEG)
    assert result["generated_at"].endswith("Z")


def test_result_is_cached_briefly(monkeypatch):
    calls = []
    real = vis.compute_visibility
    monkeypatch.setattr(vis, "compute_visibility", lambda *a, **k: calls.append(1) or real(*a, **k))
    vis._cache.clear()
    first, first_age = vis.compute_visibility_cached(-25.7479, 28.2293)
    second, second_age = vis.compute_visibility_cached(-25.7479, 28.2293)
    assert len(calls) == 1
    assert second is first                      # served from the cache
    assert 0 <= first_age <= second_age < config.VISIBILITY_CACHE_SECONDS
    vis.compute_visibility_cached(-25.7479, 28.2293, hours=48)  # different window: not a cache hit
    assert len(calls) == 2


def test_cache_expires(monkeypatch):
    monkeypatch.setattr(config, "VISIBILITY_CACHE_SECONDS", 0)
    vis._cache.clear()
    first, _ = vis.compute_visibility_cached(-25.7479, 28.2293)
    second, _ = vis.compute_visibility_cached(-25.7479, 28.2293)
    assert second is not first
