"""Pass prediction for a single named satellite."""
from skyfield.api import EarthSatellite

from backend import config
from backend.satellites.african import AFRICAN_SATELLITES
from backend.services import satellites as catalog
from backend.services.satellites import ts
from backend.services.visibility import _observer, compute_passes

# Keep "ISS" working as a shorthand in URLs.
ALIASES = {"iss": "ISS (ZARYA)"}


def resolve_satellite(name: str):
    """Find a satellite in the live catalog, falling back to the bundled African TLEs
    (which are static and only meant as an offline fallback)."""
    sat = catalog.find_satellite(ALIASES.get(name.lower(), name))
    if sat is not None:
        return sat

    for key, data in AFRICAN_SATELLITES.items():
        if key.lower() == name.lower():
            line1, line2 = data["tle"]
            return EarthSatellite(line1, line2, key, ts)
    return None


def predict_passes(name: str, lat=None, lon=None, hours: int = 24):
    """Passes of `name` over (lat, lon) in the next `hours`, or None if unknown."""
    sat = resolve_satellite(name)
    if sat is None:
        return None

    default = config.DEFAULT_OBSERVER
    lat = default["lat"] if lat is None else lat
    lon = default["lon"] if lon is None else lon
    elevation = default["elevation_m"] if (lat, lon) == (default["lat"], default["lon"]) else 0.0

    passes = compute_passes([sat], _observer(lat, lon, elevation), ts.now(), hours=hours)
    return {
        "satellite": sat.name,
        "observer": {"lat": lat, "lon": lon},
        "hours": hours,
        "passes": passes,
    }
