import json

import pytest

from backend import config
from backend.services import tle_service


def test_parse_tle_text(tle_text):
    data = tle_service.parse_tle_text(tle_text)
    iss = data["ISS (ZARYA)"]
    assert iss["norad_id"] == "25544"
    assert iss["line1"].startswith("1 25544U")
    assert iss["line2"].startswith("2 25544")


def test_parse_resyncs_after_garbage(tle_text):
    data = tle_service.parse_tle_text("garbage line\n" + tle_text)
    assert "ISS (ZARYA)" in data


def test_parse_keeps_duplicate_names():
    text = (
        "SAME\n1 00001U 00000A   25001.00000000  .00000000  00000+0  00000+0 0  9990\n"
        "2 00001   0.0000   0.0000 0000000   0.0000   0.0000 15.00000000    10\n"
        "SAME\n1 00002U 00000B   25001.00000000  .00000000  00000+0  00000+0 0  9990\n"
        "2 00002   0.0000   0.0000 0000000   0.0000   0.0000 15.00000000    10\n"
    )
    assert len(tle_service.parse_tle_text(text)) == 2


def test_get_tles_downloads_once_while_fresh(monkeypatch, tle_text):
    calls = []
    monkeypatch.setattr(tle_service, "_download", lambda: calls.append(1) or tle_text)
    tle_service.get_tles()
    tle_service.get_tles()
    assert len(calls) == 1


def test_expired_cache_is_refreshed(monkeypatch, tle_text):
    calls = []
    monkeypatch.setattr(tle_service, "_download", lambda: calls.append(1) or tle_text)
    monkeypatch.setattr(config, "TLE_TTL_SECONDS", 0)
    tle_service.get_tles()
    tle_service.get_tles()
    assert len(calls) == 2


def test_failed_refresh_serves_stale_data(monkeypatch):
    monkeypatch.setattr(config, "TLE_TTL_SECONDS", 0)
    first = tle_service.get_tles()

    def boom():
        raise ConnectionError("CelesTrak down")

    monkeypatch.setattr(tle_service, "_download", boom)
    assert tle_service.get_tles() == first


def test_failed_refresh_backs_off(monkeypatch):
    monkeypatch.setattr(config, "TLE_TTL_SECONDS", 0)
    tle_service.get_tles()
    calls = []

    def boom():
        calls.append(1)
        raise ConnectionError("down")

    monkeypatch.setattr(tle_service, "_download", boom)
    for _ in range(5):
        tle_service.get_tles()
    assert len(calls) == 1  # later requests don't re-hit the network during back-off


def test_disk_cache_used_when_network_down(monkeypatch):
    tle_service.get_tles()  # writes the disk cache
    assert config.TLE_CACHE_PATH.exists()

    tle_service.reset_for_tests()  # simulate a restart

    def boom():
        raise ConnectionError("down")

    monkeypatch.setattr(tle_service, "_download", boom)
    data = tle_service.get_tles()
    assert "ISS (ZARYA)" in data
    assert tle_service.get_tle_status()["source"] == "disk"


def test_no_data_anywhere_raises(monkeypatch):
    def boom():
        raise ConnectionError("down")

    monkeypatch.setattr(tle_service, "_download", boom)
    with pytest.raises(tle_service.TLEUnavailable):
        tle_service.get_tles()


def test_corrupt_disk_cache_is_ignored(monkeypatch):
    config.TLE_CACHE_PATH.write_text("{not json", encoding="utf-8")

    def boom():
        raise ConnectionError("down")

    monkeypatch.setattr(tle_service, "_download", boom)
    with pytest.raises(tle_service.TLEUnavailable):
        tle_service.get_tles()


def test_disk_cache_roundtrip_format():
    tle_service.get_tles()
    payload = json.loads(config.TLE_CACHE_PATH.read_text(encoding="utf-8"))
    assert "fetched_at" in payload and "ISS (ZARYA)" in payload["data"]
