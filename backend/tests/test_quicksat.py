import math

import pytest

from backend import config
from backend.services import quicksat, sky

SAMPLE = (
    "00001 d Desig...  Name.......... Mag.  Sz1 Sz2 Sz3 RCS Comments 36511\r\n"
    "00005   58 2B     Vanguard 1      9.5  0.2 0.0 0.0 .12\r\n"
    "00051 d 60 9C     Echo 1 Deb C    7.5              .60\r\n"
    "00052 t 60 9D     Tumbler         3.0  1.0 0.0 0.0 .60\r\n"
    "00053   60 9E     No Mag Row                  1.0 0.0 .56\r\n"
    "20580   90 37B    HST             1.5 13.3 4.3 0.0  35 occ flare to -4\r\n"
    "25544   98 67A    ISS            -2.0              392\r\n"
    "99999 d Desig...  Name.......... Mag.  Sz1 Sz2 Sz3 RCS Comme\r\n"
)


def test_parse_fixed_columns_and_skips():
    t = quicksat.parse(SAMPLE)
    assert t == {5: (9.5, "Vanguard 1"), 20580: (1.5, "HST"), 25544: (-2.0, "ISS")}
    # decayed (d), tumbling (t), no-magnitude rows and the header/sentinel rows are dropped


def test_conversion_to_standard_magnitude():
    assert quicksat.INTRINSIC_TO_STANDARD == pytest.approx(2.5 * math.log10(math.pi))
    # A full-phase sphere is brighter than a half-phase one by this amount
    full = sky.estimate_magnitude(quicksat.INTRINSIC_TO_STANDARD + 0.0, 1000.0, 0.0)
    assert float(full) == pytest.approx(0.0, abs=1e-6)  # std = 1.24 -> intrinsic 0.0 at phase 0


def test_real_file_loads():
    t = quicksat.table()
    assert len(t) > 2000
    assert t[25544][0] == -2.0 and t[20580][0] == 1.5


def test_missing_file_means_no_data(monkeypatch):
    monkeypatch.setattr(config, "QUICKSAT_MAG_PATH", "/definitely/not/here.mag")
    quicksat.reset_for_tests()
    try:
        assert quicksat.table() == {}
        assert quicksat.standard_magnitude(25544) is None
    finally:
        quicksat.reset_for_tests()


def test_hand_entered_figure_wins_over_file(monkeypatch):
    assert sky.standard_magnitude("ISS (ZARYA)", 25544) == config.BRIGHT_STD_MAGS["ISS (ZARYA)"]
    monkeypatch.setattr(config, "BRIGHT_STD_MAGS", {})
    assert sky.standard_magnitude("ISS (ZARYA)", 25544) == pytest.approx(-2.0 + quicksat.INTRINSIC_TO_STANDARD)


def test_unknown_object_stays_unknown():
    assert sky.standard_magnitude("STARLINK-1234", 99998) is None
    assert sky.standard_magnitude("STARLINK-1234") is None
