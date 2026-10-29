"""The fast paths must give exactly the answers of the slow, exact ones."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from backend.services import prefilter, sky
from backend.services import satellites as catalog
from backend.services import visibility as vis
from backend.tools.benchmark import synthetic_tles

OBSERVERS = [(-25.75, 28.19), (0.0, 0.0), (64.1, -21.9), (-89.0, 10.0), (35.0, 139.7)]


@pytest.fixture(scope="module")
def big_catalogue():
    # a few hundred satellites on realistic shells, built directly (no network, no disk)
    return list(catalog.build_satellites(synthetic_tles(600)).values())


@pytest.mark.parametrize("lat,lon", OBSERVERS)
def test_prefilter_gives_identical_visible_now(big_catalogue, lat, lon):
    observer = vis._observer(lat, lon)
    now = vis.ts.now()
    fast = vis.compute_visible_now(big_catalogue, observer, now, prefilter_min=0)
    exact = vis.compute_visible_now(big_catalogue, observer, now, prefilter_min=10**9)
    assert fast == exact
    assert len(exact) > 10  # the test is only meaningful if satellites are actually overhead


@pytest.mark.parametrize("lat,lon", OBSERVERS)
def test_prefilter_never_drops_a_satellite_above_the_horizon(big_catalogue, lat, lon):
    observer = vis._observer(lat, lon)
    now = vis.ts.now()
    mask = prefilter.above_horizon_mask(big_catalogue, observer, now)
    for sat, kept in zip(big_catalogue, mask):
        elevation = (sat - observer).at(now).altaz()[0].degrees
        if elevation > 0:
            assert kept, f"{sat.name} is {elevation:.2f} deg up but was dropped"


def test_prefilter_is_skipped_for_a_small_list(big_catalogue):
    observer = vis._observer(-25.75, 28.19)
    now = vis.ts.now()
    small = big_catalogue[:20]
    assert vis.compute_visible_now(small, observer, now) == vis.compute_visible_now(
        small, observer, now, prefilter_min=0
    )


def test_below_horizon_requests_are_not_filtered(big_catalogue):
    observer = vis._observer(-25.75, 28.19)
    rows = vis.compute_visible_now(big_catalogue, observer, vis.ts.now(), include_below_horizon=True)
    assert len(rows) == len(big_catalogue)


def test_shadow_test_matches_skyfield(big_catalogue):
    eph = sky.get_ephemeris()
    in_shadow = 0
    for hours in (0, 2.5, 7, 13):
        t = vis.ts.from_datetime(datetime.now(timezone.utc) + timedelta(hours=hours))
        for sat in big_catalogue:
            g = sat.at(t)
            reference = bool(g.is_sunlit(eph))
            in_shadow += not reference
            assert bool(sky.is_sunlit_geocentric(g, t)) == reference
    assert in_shadow > 100  # both outcomes were actually exercised


def test_shadow_test_accepts_an_array_of_times(big_catalogue):
    times = vis.ts.utc(2026, 10, 28, 12, range(0, 120, 10))
    lit = sky.is_sunlit(big_catalogue[0], times)
    assert lit.shape == (12,)
    eph = sky.get_ephemeris()
    assert list(lit) == [bool(big_catalogue[0].at(times[i]).is_sunlit(eph)) for i in range(12)]


def test_sun_vector_is_shared_between_calls_at_the_same_moment(big_catalogue):
    t = vis.ts.now()
    a = sky._sun_vectors(t)
    b = sky._sun_vectors(t)
    assert a is b
    c = sky._sun_vectors(vis.ts.from_datetime(datetime.now(timezone.utc) + timedelta(minutes=5)))
    assert not np.allclose(a[0], c[0])
