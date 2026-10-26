import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import africa, groups

ISS_TLE = (
    "1 25544U 98067A   25359.24512050  .00013923  00000+0  25323-3 0  9998\n"
    "2 25544  51.6316  80.5467 0003202 298.8467  61.2200 15.49803499544797\n"
)


@pytest.fixture
def tle_text(tle_text):
    """The normal fixture plus two fake 'African' satellites flying the ISS orbit."""
    return tle_text + "ZACUBE-1 (TSHEPISOSAT)\n" + ISS_TLE.replace("25544", "39417") \
        + "NIGERIASAT-2\n" + ISS_TLE.replace("25544", "37849")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize(
    "name,country",
    [
        ("ZACUBE-1 (TSHEPISOSAT)", "South Africa"),
        ("ZACUBE-2", "South Africa"),
        ("NIGERIASAT-2", "Nigeria"),
        ("NIGERIAEDUSAT-1", "Nigeria"),
        ("EGYPTSAT 2", "Egypt"),
        ("NILESAT 201", "Egypt"),
        ("TIBA-1", "Egypt"),
        ("ALSAT-1B", "Algeria"),
        ("MOHAMMED VI-A", "Morocco"),
        ("ETRSS-1", "Ethiopia"),
        ("1KUNS-PF", "Kenya"),
        ("RASCOMSTAR-QAF 1R", "Pan-African"),
    ],
)
def test_country_of(name, country):
    assert africa.country_of(name) == country
    assert groups.classify(name) == "africa"


@pytest.mark.parametrize(
    "name",
    ["STARLINK-1234", "GALSAT-1", "KONDOR-FKA 1", "ISS (ZARYA)", "TIBAL-1", "SKYSAT-C3", "NOAA 19"],
)
def test_not_african(name):
    assert africa.country_of(name) is None
    assert groups.classify(name) != "africa"


def test_word_start_matching_only():
    assert africa.country_of("XALSAT-1") is None
    assert africa.country_of("ALSAT-2A") == "Algeria"


def test_unmatched_entries_reports_misses():
    miss = africa.unmatched_entries(["ZACUBE-1", "SOMETHING ELSE"])
    prefixes = {m["prefix"] for m in miss}
    assert "ZACUBE" not in prefixes and "NIGERIA" in prefixes


def test_overview(client):
    body = client.get("/africa").json()
    names = {s["name"]: s for s in body["satellites"]}
    assert names["ZACUBE-1 (TSHEPISOSAT)"]["country"] == "South Africa"
    assert names["ZACUBE-1 (TSHEPISOSAT)"]["norad"] == 39417
    assert -90 <= names["NIGERIASAT-2"]["lat"] <= 90
    assert {c["country"] for c in body["countries"]} == {"South Africa", "Nigeria"}
    assert any(u["prefix"] == "EGYPTSAT" for u in body["unmatched"])
    assert all(u["prefix"] != "ZACUBE" for u in body["unmatched"])


def test_positions_carry_country(client):
    rows = client.get("/positions", params={"group": "africa"}).json()
    assert {r["country"] for r in rows} == {"South Africa", "Nigeria"}
    iss = client.get("/positions", params={"search": "ISS (ZARYA)"}).json()[0]
    assert "country" not in iss


def test_africa_passes(client):
    r = client.get("/africa/passes", params={"lat": 30, "lon": 20, "hours": 48})
    assert r.status_code == 200
    passes = r.json()["passes"]
    assert passes and {p["country"] for p in passes} <= {"South Africa", "Nigeria"}
    assert passes == sorted(passes, key=lambda p: p["rise_time_utc"])
    assert {"rise_time_utc", "max_elevation_deg", "visibility"} <= set(passes[0])


def test_africa_passes_validation(client):
    assert client.get("/africa/passes", params={"lat": 95, "lon": 0}).status_code == 422
    assert client.get("/africa/passes", params={"lat": 0, "lon": 0, "hours": 0}).status_code == 422
