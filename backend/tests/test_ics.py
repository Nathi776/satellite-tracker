from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.ics import passes_to_ics

PASS = {
    "name": "ISS (ZARYA)", "rise_time_utc": "2026-10-26T17:30:05Z", "peak_time_utc": "2026-10-26T17:33:00Z",
    "set_time_utc": "2026-10-26T17:36:10Z", "rise_direction": "WNW", "peak_direction": "SW",
    "set_direction": "SSE", "max_elevation_deg": 62.4, "visibility": "visible",
    "visible_from_utc": "2026-10-26T17:30:05Z", "visible_until_utc": "2026-10-26T17:35:40Z", "magnitude": -3.2,
}
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def test_event_fields_and_alarm():
    ics = passes_to_ics([PASS], -25.7, 28.2, now=NOW)
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert "DTSTART:20261026T173005Z" in ics and "DTEND:20261026T173610Z" in ics
    assert "SUMMARY:ISS (ZARYA) pass" in ics
    assert "TRIGGER:-PT10M" in ics
    assert ics.count("BEGIN:VEVENT") == ics.count("END:VEVENT") == 1


def test_escaping_and_folding():
    p = {**PASS, "name": "A,B;C\\D " + "x" * 120}
    ics = passes_to_ics([p], 0, 0, now=NOW)
    assert "A\\,B\;C\\\\D" in ics
    assert all(len(l.encode()) <= 75 for l in ics.split("\r\n"))


def test_uid_unique_per_pass():
    other = {**PASS, "rise_time_utc": "2026-10-27T17:30:05Z", "set_time_utc": "2026-10-27T17:36:10Z"}
    ics = passes_to_ics([PASS, other], 0, 0, now=NOW)
    uids = [l for l in ics.split("\r\n") if l.startswith("UID:")]
    assert len(set(uids)) == 2


def test_empty_calendar_is_valid():
    assert "BEGIN:VEVENT" not in passes_to_ics([], 0, 0, now=NOW)


def test_endpoint():
    c = TestClient(app)
    r = c.get("/passes/calendar.ics", params={"lat": -25.7, "lon": 28.2, "naked_eye_only": False, "hours": 48})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert "attachment" in r.headers["content-disposition"]
    assert r.text.count("BEGIN:VEVENT") == r.text.count("END:VEVENT")
    assert c.get("/passes/calendar.ics", params={"lat": 95, "lon": 0}).status_code == 422
