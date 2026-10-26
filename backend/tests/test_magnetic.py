from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.magnetic import declination_deg

WHEN = datetime(2026, 10, 1, tzinfo=timezone.utc)


# Approximate World Magnetic Model values (degrees, east positive); a generous tolerance
# because the field drifts and published figures differ by a degree or so.
@pytest.mark.parametrize(
    "lat,lon,expected",
    [(-25.75, 28.19, -20.2), (-33.9, 18.4, -26.8), (51.5, -0.1, 1.2), (40.7, -74.0, -12.5), (-1.3, 36.8, 0.3)],
)
def test_known_cities(lat, lon, expected):
    assert declination_deg(lat, lon, WHEN) == pytest.approx(expected, abs=1.5)


def test_endpoint():
    c = TestClient(app)
    body = c.get("/observer/declination", params={"lat": -25.75, "lon": 28.19}).json()
    assert -23 < body["declination_deg"] < -17
    assert c.get("/observer/declination", params={"lat": 91, "lon": 0}).status_code == 422


def test_visibility_reports_declination():
    c = TestClient(app)
    obs = c.get("/observer/visibility", params={"lat": -25.75, "lon": 28.19}).json()["observer"]
    assert -23 < obs["declination_deg"] < -17
