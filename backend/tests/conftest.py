from pathlib import Path

import pytest

from backend import config, ratelimit
from backend.services import alerts, pushsender, satcat
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
    # The background thread is tested on its own (test_refresher.py); everything else
    # keeps the simple "first request loads the data" behaviour.
    monkeypatch.setattr(config, "REFRESH_IN_BACKGROUND", False)
    # the rate limit has its own tests (test_ratelimit.py)
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 0)
    ratelimit.buckets.reset()
    # no SATCAT downloads or disk cache in tests
    monkeypatch.setattr(config, "SATCAT_URL", "")
    monkeypatch.setattr(config, "SATCAT_CACHE_PATH", tmp_path / "satcat_cache.json")
    satcat.reset_for_tests()
    # push alerts: temp database and VAPID key, no background thread
    monkeypatch.setattr(config, "PUSH_DB_PATH", tmp_path / "push.db")
    monkeypatch.setattr(config, "VAPID_KEY_PATH", tmp_path / "vapid.pem")
    monkeypatch.setattr(config, "VAPID_PRIVATE_KEY", "")
    monkeypatch.setattr(pushsender, "_vapid", None)
    monkeypatch.setattr(alerts, "start", lambda: None)
    alerts._cache.clear()
    tle_service.reset_for_tests()
    catalog._cache.update(version=None, snapshot=({}, [], {}))
    yield
    tle_service.reset_for_tests()
