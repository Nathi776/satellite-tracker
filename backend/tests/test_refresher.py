"""The background refresher: requests never wait for a download or a catalogue rebuild."""
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from backend import config
from backend.services import refresher
from backend.services import satellites as catalog
from backend.services import tle_service


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    yield
    refresher.stop()


def _age_the_data(seconds):
    with tle_service._lock:
        tle_service._state["last_updated"] = datetime.now(timezone.utc) - timedelta(seconds=seconds)


def test_requests_do_not_download_stale_data_while_background_runs(monkeypatch):
    tle_service.get_tles()  # load once
    tle_service.set_background(True)
    _age_the_data(config.TLE_TTL_SECONDS + 100)
    calls = []
    monkeypatch.setattr(tle_service, "_download", lambda: calls.append(1) or "")
    assert tle_service.get_tles()  # served, however old
    assert calls == []


def test_stale_data_is_still_downloaded_by_requests_without_the_refresher(monkeypatch, tle_text):
    tle_service.get_tles()
    _age_the_data(config.TLE_TTL_SECONDS + 100)
    calls = []
    monkeypatch.setattr(tle_service, "_download", lambda: calls.append(1) or tle_text)
    tle_service.get_tles()
    assert calls == [1]


def test_catalogue_swaps_only_when_the_new_one_is_ready(monkeypatch, tle_text):
    tle_service.set_background(True)
    tle_service.load_cached() or tle_service.refresh_in_background()
    old = catalog.get_satellites()
    old_version = catalog.get_version()

    # new data arrives (version bumps) but the build is slow
    release = threading.Event()
    real_build = catalog.build_satellites

    def slow_build(tles):
        release.wait(5)
        return real_build(tles)

    monkeypatch.setattr(catalog, "build_satellites", slow_build)
    tle_service.refresh_in_background()
    builder = threading.Thread(target=catalog.warm)
    builder.start()
    time.sleep(0.1)

    started = time.monotonic()
    assert catalog.get_satellites() is old  # old catalogue, immediately
    assert time.monotonic() - started < 0.5
    assert catalog.get_version() == old_version

    release.set()
    builder.join(5)
    assert catalog.get_satellites() is not old
    assert catalog.get_version() == tle_service.get_version()


def test_failed_refresh_keeps_serving_and_reports_the_error(monkeypatch):
    tle_service.set_background(True)
    tle_service.refresh_in_background()
    catalog.warm()
    before = catalog.get_satellites()

    def boom():
        raise ConnectionError("celestrak down")

    monkeypatch.setattr(tle_service, "_download", boom)
    with pytest.raises(ConnectionError):
        refresher.refresh_once()
    assert catalog.get_satellites() is before
    status = tle_service.get_tle_status()
    assert "celestrak down" in status["last_error"]
    assert status["refreshing"] is False and status["loaded"]


def test_retry_delay_grows_and_is_capped():
    assert refresher._retry_delay(1) == refresher.RETRY_BASE_SECONDS
    assert refresher._retry_delay(2) == 2 * refresher.RETRY_BASE_SECONDS
    assert refresher._retry_delay(30) == refresher.RETRY_MAX_SECONDS


def test_startup_uses_the_disk_copy_without_waiting_for_the_network(monkeypatch, tle_text):
    tle_service.get_tles()  # writes the disk cache
    tle_service.reset_for_tests()
    catalog._cache.update(version=None, snapshot=({}, [], {}))

    def hang():
        raise AssertionError("startup must not download when a disk copy exists")

    monkeypatch.setattr(tle_service, "_download", hang)
    refresher._startup()
    assert tle_service.get_tle_status()["source"] == "disk"
    assert catalog.get_satellites()


def test_thread_refreshes_stale_data_and_stops_cleanly(monkeypatch, tle_text):
    tle_service.get_tles()
    _age_the_data(config.TLE_TTL_SECONDS + 100)
    downloads = []
    monkeypatch.setattr(tle_service, "_download", lambda: downloads.append(1) or tle_text)
    refresher.start()
    deadline = time.monotonic() + 10
    while not downloads and time.monotonic() < deadline:
        time.sleep(0.05)
    assert downloads, "the refresher should have downloaded the stale data"
    deadline = time.monotonic() + 10
    while catalog.get_version() != tle_service.get_version() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert catalog.get_version() == tle_service.get_version()
    refresher.stop()
    assert tle_service.get_tle_status()["background_refresh"] is False


def test_health_reports_refresh_state():
    tle_service.set_background(True)
    tle_service.refresh_in_background()
    status = tle_service.get_tle_status()
    assert status["background_refresh"] is True
    assert 0 < status["next_refresh_in_seconds"] <= config.TLE_TTL_SECONDS
