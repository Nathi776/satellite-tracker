import math
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from skyfield.api import wgs84

from backend.main import app
from backend.services import groups
from backend.services import satellites as catalog
from backend.services.orbit_service import EARTH_RADIUS_KM, footprint_radius_km
from backend.services.satellites import ts


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name, expected", [
    ("ISS (ZARYA)", "stations"),
    ("ISS (NAUKA)", "stations"),
    ("CSS (TIANHE)", "stations"),
    ("CSS (WENTIAN)", "stations"),
    ("PROGRESS MS-30", "stations"),
    ("SHENZHOU-19", "stations"),
    ("ZACUBE-1 (TSHEPISOSAT)", "africa"),
    ("NIGERIASAT-2", "africa"),
    ("EGYPTSAT 2", "africa"),
    ("NILESAT 201", "africa"),       # would also match "comms": Africa must win
    ("ANGOSAT-2", "africa"),
    ("MOHAMMED VI-A", "africa"),
    ("NOAA 19", "weather"),
    ("GOES 18", "weather"),
    ("METEOSAT-11 (MSG-4)", "weather"),
    ("FENGYUN 3D", "weather"),
    ("NAVSTAR 81 (USA 319)", "navigation"),
    ("GSAT0211 (GALILEO 15)", "navigation"),
    ("BEIDOU-3 M1", "navigation"),
    ("COSMOS 2545 (GLONASS-K)", "navigation"),
    ("STARLINK-31234", "starlink"),
    ("ONEWEB-0123", "oneweb"),
    ("IRIDIUM 106", "comms"),
    ("INTELSAT 39", "comms"),
    ("HST", "other"),
    ("FREGAT DEB", "other"),
    ("1998-067XS", "other"),
])
def test_classify(name, expected):
    assert groups.classify(name) == expected


def test_every_satellite_gets_exactly_one_known_group(tle_text):
    cat = catalog.get_satellites()
    assigned = catalog.get_groups()
    assert set(assigned) == set(cat)
    assert set(assigned.values()) <= set(groups.ORDER)


def test_summary_counts_add_up():
    catalog.get_satellites()
    summary = catalog.group_summary()
    assert [g["id"] for g in summary] == groups.ORDER          # stable display order
    assert sum(g["count"] for g in summary) == len(catalog.get_satellites())


# ---------------------------------------------------------------------------
# select()
# ---------------------------------------------------------------------------
def test_select_filters_before_limiting():
    """The first satellites in the file are not stations; a limit must not hide the ones
    that come later."""
    all_stations = catalog.select(group="stations")
    assert 1 <= len(all_stations) < len(catalog.get_satellites())
    assert all(groups.classify(s.name) == "stations" for s in all_stations)
    assert [s.name for s in catalog.select(group="stations", limit=1)] == [all_stations[0].name]


def test_select_search_and_group_combine():
    names = [s.name for s in catalog.select(search="iss", group="stations")]
    assert names and all("ISS" in n for n in names)
    assert catalog.select(search="iss", group="weather") == []


# ---------------------------------------------------------------------------
# footprint
# ---------------------------------------------------------------------------
def test_footprint_radius_known_values():
    assert footprint_radius_km(0) == 0
    # ISS (~420 km): the horizon is ~2,300 km from the sub-satellite point
    assert 2250 < footprint_radius_km(420) < 2400
    # a geostationary satellite sees a bit under 9,000 km from its sub-point (about 81 deg of arc)
    geo = footprint_radius_km(35786)
    assert 8900 < geo < 9100
    assert geo / EARTH_RADIUS_KM < math.pi / 2          # always less than a quarter of the Earth


def test_positions_report_footprint_and_group(client):
    iss = client.get("/positions", params={"search": "iss (zarya)"}).json()[0]
    assert iss["group"] == "stations"
    assert math.isclose(iss["footprint_km"], footprint_radius_km(iss["alt_km"]), abs_tol=1)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def test_groups_endpoint(client):
    body = client.get("/groups").json()
    assert body[0]["id"] == "all" and body[0]["count"] == len(catalog.get_satellites())
    assert [g["id"] for g in body[1:]] == groups.ORDER
    assert sum(g["count"] for g in body[1:]) == body[0]["count"]


def test_positions_group_filter(client):
    rows = client.get("/positions", params={"group": "stations"}).json()
    assert rows and all(r["group"] == "stations" for r in rows)
    everything = client.get("/positions", params={"group": "all", "limit": 2000}).json()
    assert len(everything) >= len(rows)


def test_unknown_group_is_422(client):
    assert client.get("/positions", params={"group": "nonsense"}).status_code == 422


def test_positions_limit_may_now_reach_2000(client):
    assert client.get("/positions", params={"limit": 2000}).status_code == 200
    assert client.get("/positions", params={"limit": 2001}).status_code == 422


# ---------------------------------------------------------------------------
# time travel
# ---------------------------------------------------------------------------
def test_positions_at_matches_independent_skyfield_calculation(client):
    at = datetime.now(timezone.utc) + timedelta(hours=3)
    row = client.get("/positions", params={"search": "iss (zarya)", "at": iso(at)}).json()[0]

    sat = catalog.find_satellite("ISS (ZARYA)")
    sub = wgs84.subpoint(sat.at(ts.from_datetime(at.replace(microsecond=0))))
    assert math.isclose(row["lat"], sub.latitude.degrees, abs_tol=0.01)
    assert math.isclose(row["lon"], sub.longitude.degrees, abs_tol=0.01)


def test_time_travel_actually_moves_the_satellite(client):
    now_row = client.get("/positions", params={"search": "iss (zarya)"}).json()[0]
    later = datetime.now(timezone.utc) + timedelta(minutes=30)
    later_row = client.get("/positions", params={"search": "iss (zarya)", "at": iso(later)}).json()[0]
    assert (now_row["lat"], now_row["lon"]) != (later_row["lat"], later_row["lon"])


def test_at_without_timezone_is_read_as_utc(client):
    at = datetime.now(timezone.utc) + timedelta(hours=1)
    naive = at.strftime("%Y-%m-%dT%H:%M:%S")
    a = client.get("/positions", params={"search": "iss (zarya)", "at": naive}).json()[0]
    b = client.get("/positions", params={"search": "iss (zarya)", "at": naive + "Z"}).json()[0]
    assert (a["lat"], a["lon"]) == (b["lat"], b["lon"])


@pytest.mark.parametrize("hours", [-49, 49, 24 * 30])
def test_at_too_far_from_now_is_422(client, hours):
    at = datetime.now(timezone.utc) + timedelta(hours=hours)
    r = client.get("/positions", params={"at": iso(at)})
    assert r.status_code == 422 and "within" in r.json()["detail"]


def test_at_garbage_is_422(client):
    assert client.get("/positions", params={"at": "yesterday-ish"}).status_code == 422


def test_groundtrack_starts_at_requested_time(client):
    at = datetime.now(timezone.utc) + timedelta(hours=2)
    track = client.get("/groundtrack/ISS", params={"at": iso(at), "minutes": 10, "step": 2}).json()["track"]
    first = client.get("/positions", params={"search": "iss (zarya)", "at": iso(at)}).json()[0]
    assert math.isclose(track[0]["lat"], first["lat"], abs_tol=0.01)
    assert math.isclose(track[0]["lon"], first["lon"], abs_tol=0.01)


# ---- several groups at once -------------------------------------------------
def test_group_ids_parsing():
    assert catalog.group_ids(None) == []
    assert catalog.group_ids("all") == []
    assert catalog.group_ids("stations, weather,stations") == ["stations", "weather"]
    assert catalog.group_ids(["stations", "all"]) == []


def test_select_several_groups_is_the_union():
    counts = {g["id"]: g["count"] for g in catalog.group_summary()}
    two = [g for g in counts if counts[g] > 0 and g != "all"][:2]
    assert len(two) == 2
    union = catalog.select(group=two)
    assert len(union) == counts[two[0]] + counts[two[1]]
    assert {catalog.get_groups()[s.name] for s in union} == set(two)


def test_fair_shares_do_not_let_one_group_take_everything():
    shares = catalog._fair_shares({"big": 1800, "small": 12, "mid": 150}, 100)
    assert shares["small"] == 12
    assert sum(shares.values()) == 100
    assert shares["mid"] == shares["big"] == 44


def test_api_accepts_comma_separated_groups(client_factory=None):
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as c:
        groups_seen = {g["id"] for g in c.get("/groups").json() if g["count"] > 0 and g["id"] != "all"}
        pick = sorted(groups_seen)[:2]
        r = c.get("/positions", params={"group": ",".join(pick), "limit": 2000})
        assert r.status_code == 200
        assert {s["group"] for s in r.json()} <= set(pick)
        assert c.get("/positions", params={"group": f"{pick[0]},nonsense"}).status_code == 422
