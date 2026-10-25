import numpy as np
import pytest
from skyfield.api import wgs84

from backend.services import sky
from backend.services import satellites as catalog
from backend.services.satellites import ts

PRETORIA = wgs84.latlon(-25.7479, 28.2293, elevation_m=1350)


def iss():
    return catalog.find_satellite("ISS")


def test_sun_is_high_at_noon_and_far_below_at_midnight():
    # 21 Dec: the Sun is almost overhead in Pretoria (latitude 25.7 S, declination 23.4 S)
    noon = float(sky.sun_altitude_deg(PRETORIA, ts.utc(2025, 12, 21, 10, 5)))
    midnight = float(sky.sun_altitude_deg(PRETORIA, ts.utc(2025, 12, 21, 22, 5)))
    assert 86 < noon <= 88.5
    assert midnight < -35


def test_sun_altitude_accepts_arrays():
    times = ts.utc(2025, 12, 21, range(0, 24))
    alts = sky.sun_altitude_deg(PRETORIA, times)
    assert alts.shape == (24,)
    assert alts.max() > 80 and alts.min() < -30


@pytest.mark.parametrize("alt,expected", [
    (45, "day"), (0, "day"), (-3, "twilight_civil"), (-6, "twilight_civil"),
    (-6.1, "twilight_nautical"), (-12.1, "twilight_astronomical"), (-18.1, "night"),
])
def test_sky_state(alt, expected):
    assert sky.sky_state(alt) == expected


def test_dark_enough_uses_configured_threshold():
    assert bool(sky.is_dark_enough(-10)) is True
    assert bool(sky.is_dark_enough(-2)) is False


def test_iss_spends_part_of_every_orbit_in_earths_shadow():
    t0 = ts.utc(2025, 12, 26, 12)
    times = ts.tt_jd(t0.tt + np.arange(0, 93) / 1440.0)
    lit = sky.is_sunlit(iss(), times)
    assert lit.shape == (93,)
    assert lit.any() and not lit.all()
    assert 0.5 < lit.mean() < 0.75  # ISS is in sunlight roughly 60% of its orbit


def test_phase_angle_is_between_0_and_180_degrees():
    times = ts.tt_jd(ts.utc(2025, 12, 26, 12).tt + np.arange(0, 60) / 1440.0)
    phase = sky.phase_angle_rad(iss(), PRETORIA, times)
    assert phase.shape == (60,)
    assert np.all(phase >= 0) and np.all(phase <= np.pi)


def test_magnitude_model():
    # by definition: the standard magnitude is the brightness at 1000 km, half illuminated
    assert float(sky.estimate_magnitude(-1.8, 1000, np.pi / 2)) == pytest.approx(-1.8)
    # closer is brighter (5 magnitudes per factor of 100 in distance)
    assert float(sky.estimate_magnitude(-1.8, 100, np.pi / 2)) == pytest.approx(-6.8)
    # a fuller phase is brighter than a thin crescent
    full = float(sky.estimate_magnitude(0, 1000, np.radians(30)))
    crescent = float(sky.estimate_magnitude(0, 1000, np.radians(150)))
    assert full < crescent
    # no log(0) blow-up at the extreme
    assert np.isfinite(sky.estimate_magnitude(0, 1000, np.pi))


def test_standard_magnitude_lookup_ignores_case_and_punctuation():
    assert sky.standard_magnitude("iss zarya") == sky.standard_magnitude("ISS (ZARYA)")
    assert sky.standard_magnitude("ISS (ZARYA)") is not None
    assert sky.standard_magnitude("SOME CUBESAT") is None


def test_unknown_brightness_is_never_bright_enough():
    assert sky.is_bright_enough(None) is False
    assert bool(sky.is_bright_enough(-3.0)) is True
    assert bool(sky.is_bright_enough(7.0)) is False


@pytest.mark.parametrize("az,point", [
    (0, "N"), (11, "N"), (12, "NNE"), (90, "E"), (180, "S"), (225, "SW"), (270, "W"), (359, "N"), (-90, "W"),
])
def test_compass_point(az, point):
    assert sky.compass_point(az) == point
