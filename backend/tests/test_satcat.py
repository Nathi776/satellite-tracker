"""Size-based brightness: the fit, the parsing, the source order and the naked-eye margin."""
import json
import math
import time

import numpy as np
import pytest

from backend import config
from backend.services import quicksat, satcat, sky

CSV = (
    "OBJECT_NAME,OBJECT_ID,NORAD_CAT_ID,OBJECT_TYPE,OPS_STATUS_CODE,OWNER,RCS\n"
    "STARLINK-1007,2019-074A,44713,PAY,+,US,6.7\n"
    "SMALL THING,2020-001A,45000,PAY,+,US,0.02\n"
    "NO SIZE,2020-002A,45001,PAY,+,US,\n"
    "BAD ROW,2020-003A,notanumber,PAY,+,US,5\n"
)


def test_parse_csv_reads_columns_by_name_and_skips_bad_rows():
    assert satcat.parse_csv(CSV) == {44713: 6.7, 45000: 0.02}


def test_parse_csv_tolerates_other_column_order_and_garbage():
    text = "RCS,NORAD_CAT_ID\n12.5,100\n"
    assert satcat.parse_csv(text) == {100: 12.5}
    assert satcat.parse_csv("not,a,satcat\n1,2,3\n") == {}
    assert satcat.parse_csv("") == {}


def test_constants_match_a_fresh_fit_of_the_quicksat_file():
    """If someone updates quicksat.mag, re-derive STD_MAG_AT_1M2 / STD_MAG_PER_DECADE."""
    text = open(config.QUICKSAT_MAG_PATH, encoding="latin-1").read()
    rows = np.array(list(quicksat.parse_rcs(text).values()))
    assert len(rows) > 800
    x = np.log10(rows[:, 1])
    y = rows[:, 0] + quicksat.INTRINSIC_TO_STANDARD
    slope, intercept = np.polyfit(x, y, 1)
    assert -slope == pytest.approx(satcat.STD_MAG_PER_DECADE, abs=0.15)
    assert intercept == pytest.approx(satcat.STD_MAG_AT_1M2, abs=0.15)
    assert (y - (slope * x + intercept)).std() < 1.1  # the scatter the docstring promises


def test_bigger_objects_are_brighter_and_tiny_ones_are_clamped():
    assert satcat.std_mag_from_rcs(20) < satcat.std_mag_from_rcs(2) < satcat.std_mag_from_rcs(0.2)
    assert satcat.std_mag_from_rcs(0.0001) == satcat.std_mag_from_rcs(satcat.MIN_RCS_M2)
    # a Starlink-sized object (a few m²) comes out near the ~5.5 people measure for them
    assert 5.0 < satcat.std_mag_from_rcs(6.7) < 6.2


def test_source_order_manual_then_quicksat_then_size(monkeypatch):
    monkeypatch.setattr(satcat, "_loaded", {25544: 400.0, 44713: 6.7})
    assert sky.standard_magnitude_info("ISS (ZARYA)", 25544)[1] == "manual"
    monkeypatch.setattr(config, "BRIGHT_STD_MAGS", {})
    assert sky.standard_magnitude_info("ISS", 25544)[1] == "quicksat"  # in quicksat.mag
    mag, source = sky.standard_magnitude_info("STARLINK-1007", 44713)  # newer than quicksat
    assert source == "size" and mag == pytest.approx(satcat.std_mag_from_rcs(6.7))
    assert sky.standard_magnitude_info("UNKNOWN", 99998) == (None, None)


def test_size_estimates_need_a_margin_to_count_as_naked_eye():
    limit = config.NAKED_EYE_LIMIT_MAG
    just_inside = limit - 0.1
    assert sky.is_bright_enough(just_inside, "quicksat")
    assert not sky.is_bright_enough(just_inside, "size")
    assert sky.is_bright_enough(limit - satcat.NAKED_EYE_MARGIN_MAG - 0.1, "size")
    assert not sky.is_bright_enough(None, "size")


def test_refresh_downloads_when_missing_then_uses_the_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SATCAT_URL", "https://example.invalid/satcat.csv")
    calls = []
    monkeypatch.setattr(satcat, "_download", lambda: calls.append(1) or CSV)
    assert satcat.refresh_if_stale() is True
    assert satcat.table() == {44713: 6.7, 45000: 0.02}
    assert satcat.refresh_if_stale() is False  # fresh: no second download
    assert calls == [1]
    saved = json.loads((tmp_path / "satcat_cache.json").read_text())
    assert saved["rcs"]["44713"] == 6.7

    satcat.reset_for_tests()  # a new process: the disk copy is used without the network
    assert satcat.table()[44713] == 6.7
    assert satcat.refresh_if_stale() is False and calls == [1]


def test_refresh_after_the_ttl_and_failures_keep_the_old_data(monkeypatch):
    monkeypatch.setattr(config, "SATCAT_URL", "https://example.invalid/satcat.csv")
    monkeypatch.setattr(satcat, "_download", lambda: CSV)
    satcat.refresh_if_stale()
    later = time.time() + config.SATCAT_TTL_SECONDS + 5

    def boom():
        raise ConnectionError("down")

    monkeypatch.setattr(satcat, "_download", boom)
    assert satcat.refresh_if_stale(now=later) is False
    assert satcat.table()[44713] == 6.7  # still there

    monkeypatch.setattr(satcat, "_download", lambda: "garbage\n")
    assert satcat.refresh_if_stale(now=later) is False
    assert satcat.table()[44713] == 6.7


def test_disabled_when_url_is_empty(monkeypatch):
    monkeypatch.setattr(config, "SATCAT_URL", "")
    called = []
    monkeypatch.setattr(satcat, "_download", lambda: called.append(1) or CSV)
    assert satcat.refresh_if_stale() is False and not called


def test_api_reports_size_based_source_for_new_satellites(monkeypatch):
    """A satellite newer than quicksat.mag gets a "size" figure once the SATCAT lists its RCS."""
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.services import satellites as catalog

    monkeypatch.setattr(config, "BRIGHT_STD_MAGS", {})
    with TestClient(app) as client:
        sats = catalog.get_satellites()
        newer = [s for s in sats.values() if s.model.satnum > 36511 and not quicksat.standard_magnitude(s.model.satnum)]
        if not newer:
            pytest.skip("fixture has no satellite newer than quicksat.mag")
        sat = newer[0]
        monkeypatch.setattr(satcat, "_loaded", {sat.model.satnum: 30.0})
        r = client.get("/satellite/" + sat.name + "/view", params={"lat": -25.75, "lon": 28.19})
        assert r.status_code == 200
        look = r.json()["look"]
        assert look["magnitude_source"] == "size"
        assert look["magnitude"] is not None
