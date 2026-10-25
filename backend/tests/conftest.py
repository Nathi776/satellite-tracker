from pathlib import Path

import pytest

from backend import config
from backend.services import satellites as catalog
from backend.services import tle_service

FIXTURE = Path(__file__).parent / "fixtures" / "stations.txt"


@pytest.fixture
def tle_text():
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def offline_tles(monkeypatch, tmp_path, tle_text):
    """Every test runs offline: 'downloads' return the fixture and the disk cache is a temp file."""
    monkeypatch.setattr(config, "TLE_CACHE_PATH", tmp_path / "tle_cache.json")
    monkeypatch.setattr(tle_service, "_download", lambda: tle_text)
    tle_service.reset_for_tests()
    catalog._cache.update(version=None, snapshot=({}, [], {}))
    yield
    tle_service.reset_for_tests()
