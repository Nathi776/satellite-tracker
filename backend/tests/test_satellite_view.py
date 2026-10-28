import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _iss_ground_point(client):
    pos = client.get("/satellite/ISS").json()["position"]
    return pos["lat"], pos["lon"]


def _wrap(lon):
    return (lon + 180) % 360 - 180


def test_view_straight_below_the_satellite_is_overhead(client):
    lat, lon = _iss_ground_point(client)
    r = client.get("/satellite/ISS/view", params={"lat": lat, "lon": lon})
    assert r.status_code == 200
    look = r.json()["look"]
    assert look["above_horizon"] is True
    assert look["altitude_deg"] > 80
    assert 300 < look["distance_km"] < 700  # roughly the ISS altitude
    assert look["direction"] in {"N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                                 "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"}


def test_view_on_the_other_side_of_the_earth_is_below_the_horizon(client):
    lat, lon = _iss_ground_point(client)
    r = client.get("/satellite/ISS/view", params={"lat": -lat, "lon": _wrap(lon + 180)})
    assert r.status_code == 200
    look = r.json()["look"]
    assert look["above_horizon"] is False
    assert look["altitude_deg"] < -60
    assert look["distance_km"] > 10000


def test_view_includes_the_next_pass_and_sky(client):
    r = client.get("/satellite/ISS/view", params={"lat": -25.75, "lon": 28.19, "hours": 72})
    body = r.json()
    assert body["sky"] in {"day", "twilight_civil", "twilight_nautical", "twilight_astronomical", "night"}
    p = body["next_pass"]
    assert p is not None  # the ISS passes over Pretoria within 3 days
    assert p["rise_time_utc"] < p["peak_time_utc"] < p["set_time_utc"]
    assert p["max_elevation_deg"] >= 10


def test_view_unknown_satellite_is_404_and_bad_coordinates_are_422(client):
    assert client.get("/satellite/NOPE-123/view", params={"lat": 0, "lon": 0}).status_code == 404
    assert client.get("/satellite/ISS/view", params={"lat": 95, "lon": 0}).status_code == 422
    assert client.get("/satellite/ISS/view").status_code == 422


def test_visible_now_still_excludes_satellites_below_the_horizon():
    from backend.services import satellites as catalog
    from backend.services import visibility as vis
    from backend.services.satellites import ts

    sats = list(catalog.get_satellites().values())
    observer = vis._observer(0.0, 0.0)
    now = ts.now()
    above = vis.compute_visible_now(sats, observer, now)
    everything = vis.compute_visible_now(sats, observer, now, include_below_horizon=True)
    assert all(s["altitude_deg"] > 0 for s in above)
    assert len(everything) >= len(above)


def test_view_lists_several_upcoming_passes(client):
    body = client.get("/satellite/ISS/view", params={"lat": -25.75, "lon": 28.19, "hours": 72}).json()
    assert 1 <= len(body["passes"]) <= 5
    assert body["passes"][0] == body["next_pass"]
    rises = [p["rise_time_utc"] for p in body["passes"]]
    assert rises == sorted(rises)


def test_info_has_plausible_iss_orbit(client):
    r = client.get("/satellite/ISS/info")
    assert r.status_code == 200
    i = r.json()
    assert i["norad_id"] == 25544
    assert 51 < i["inclination_deg"] < 52
    assert 90 < i["period_min"] < 94
    assert 380 < i["perigee_km"] <= i["apogee_km"] < 460
    assert i["group"] == "stations"
    assert "Space Station" in i["description"]
    assert client.get("/satellite/NOPE-123/info").status_code == 404


def test_positions_by_exact_names(client):
    r = client.get("/positions", params=[("names", "ISS (ZARYA)"), ("names", "NOT A SAT"), ("names", "ISS (ZARYA)")])
    assert r.status_code == 200
    assert [s["name"] for s in r.json()] == ["ISS (ZARYA)"]
    assert client.get("/positions", params={"names": "NOT A SAT"}).json() == []
