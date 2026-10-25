import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_root_and_health(client):
    assert client.get("/").status_code == 200
    body = client.get("/health").json()
    assert body["status"] == "ok" and "tle" in body


def test_positions_search_is_loose(client):
    r = client.get("/positions", params={"search": "iss zarya"})
    assert r.status_code == 200
    names = [s["name"] for s in r.json()]
    assert "ISS (ZARYA)" in names
    assert {"name", "lat", "lon", "alt_km", "speed_kms", "period_min"} <= set(r.json()[0])


def test_positions_limit_and_validation(client):
    assert len(client.get("/positions", params={"limit": 2}).json()) <= 2
    assert client.get("/positions", params={"limit": 0}).status_code == 422


def test_unknown_satellite_is_404_not_200(client):
    assert client.get("/groundtrack/definitely-not-a-satellite").status_code == 404
    assert client.get("/satellite/definitely-not-a-satellite").status_code == 404
    assert client.get("/passes/african/definitely-not-a-satellite").status_code == 404


def test_previously_broken_endpoints_work(client):
    iss = client.get("/iss")
    assert iss.status_code == 200 and iss.json()["name"] == "ISS (ZARYA)"
    sat = client.get("/satellite/ISS")
    assert sat.status_code == 200 and "position" in sat.json()


def test_groundtrack(client):
    r = client.get("/groundtrack/ISS")
    assert r.status_code == 200
    assert r.json()["satellite"] == "ISS (ZARYA)" and len(r.json()["track"]) > 10


def test_visibility_response_shape(client):
    r = client.get("/observer/visibility", params={"lat": -25.7479, "lon": 28.2293})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"observer", "visible_now", "next_passes"}
    for sat in body["visible_now"]:
        assert {"lat", "lon", "altitude_deg", "azimuth_deg", "distance_km"} <= set(sat)
        assert sat["altitude_deg"] > 0
    for p in body["next_passes"]:
        assert {"name", "rise_time_utc", "peak_time_utc", "set_time_utc",
                "max_elevation_deg"} <= set(p)
        assert p["rise_time_utc"] < p["peak_time_utc"] < p["set_time_utc"]
        assert p["max_elevation_deg"] >= 10


@pytest.mark.parametrize("params", [
    {"lat": 91, "lon": 0},
    {"lat": 0, "lon": 181},
    {"lat": "abc", "lon": 0},
    {"lon": 0},
])
def test_visibility_rejects_bad_coordinates(client, params):
    assert client.get("/observer/visibility", params=params).status_code == 422


def test_iss_passes_for_custom_observer(client):
    r = client.get("/passes/iss", params={"lat": -33.9, "lon": 18.4})
    assert r.status_code == 200
    assert r.json()["observer"] == {"lat": -33.9, "lon": 18.4}


def test_503_when_no_tles_at_all(monkeypatch, client):
    from backend import config
    from backend.services import tle_service

    def boom():
        raise ConnectionError("down")

    monkeypatch.setattr(tle_service, "_download", boom)
    tle_service.reset_for_tests()
    config.TLE_CACHE_PATH.unlink(missing_ok=True)  # the startup warm-up may have written one
    r = client.get("/positions")
    assert r.status_code == 503
    assert "No TLE data" in r.json()["detail"]
