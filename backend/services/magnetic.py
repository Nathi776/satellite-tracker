"""Magnetic declination: how far a compass needle points away from true north.

A phone's compass reports MAGNETIC north. In Pretoria that is about 20 degrees west of true north,
so without this correction a satellite overlay would be ~20 degrees off. Positive = magnetic north
lies EAST of true north (true azimuth = magnetic azimuth + declination).

Uses the World Magnetic Model through `pygeomag` (pure Python, ships its own coefficients).
"""
from datetime import datetime, timezone

from pygeomag import GeoMag

_geomag = GeoMag()


def declination_deg(lat: float, lon: float, when: datetime | None = None, alt_km: float = 0.0) -> float:
    when = when or datetime.now(timezone.utc)
    year = when.year + (when.timetuple().tm_yday - 1) / 366.0
    return float(_geomag.calculate(glat=lat, glon=lon, alt=alt_km, time=year).d)
