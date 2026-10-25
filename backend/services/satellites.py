"""The shared satellite catalog.

EarthSatellite objects are built once per TLE refresh and reused by every
endpoint, instead of being rebuilt from raw TLE text on each request.
"""
import logging
import re
import threading

from skyfield.api import EarthSatellite, load

from backend.services import groups, tle_service

log = logging.getLogger(__name__)

# One timescale for the whole app.
ts = load.timescale()

_lock = threading.Lock()
# "snapshot" is (satellites, name index, group per name) and is replaced as a single
# object, so readers never see parts of it from two different refreshes.
_cache = {"version": None, "snapshot": ({}, [], {})}


def _normalize(text: str) -> str:
    """'ZACUBE-1 (TSHEPISOSAT)' -> 'zacube1tshepisosat' so loose searches match."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def build_satellites(tle_dict: dict) -> dict:
    """Turn a TLE dict into {name: EarthSatellite}, skipping entries Skyfield rejects."""
    satellites = {}
    for name, tle in tle_dict.items():
        try:
            satellites[name] = EarthSatellite(tle["line1"], tle["line2"], name, ts)
        except Exception as exc:
            log.warning("Skipping %s: %s", name, exc)
    return satellites


def _snapshot():
    tles = tle_service.get_tles()  # may refresh; raises TLEUnavailable if nothing is available
    version = tle_service.get_version()

    with _lock:
        if _cache["version"] != version:
            satellites = build_satellites(tles)
            index = [(_normalize(name), name) for name in satellites]
            _cache["snapshot"] = (satellites, index, groups.classify_all(satellites))
            _cache["version"] = version
            log.info("Built %d EarthSatellite objects", len(satellites))
        return _cache["snapshot"]


def get_satellites() -> dict:
    """Return {name: EarthSatellite}, rebuilt only when the underlying TLEs changed."""
    return _snapshot()[0]


def search_satellites(query: str, limit=None) -> list:
    """Satellites whose name contains `query` (case, spaces and punctuation ignored)."""
    satellites, index, _groups = _snapshot()
    q = _normalize(query or "")
    if not q:
        matches = list(satellites.values())
    else:
        matches = [satellites[name] for norm, name in index if q in norm]
    return matches[:limit] if limit else matches


def match_prefixes(prefixes) -> list:
    """Satellites whose normalised name starts with any of the given names.

    Used for watchlists such as "ZACUBE" -> ZACUBE-1, ZACUBE-2. Order follows the
    catalog and each satellite appears once.
    """
    satellites, index, _groups = _snapshot()
    wanted = [p for p in (_normalize(x) for x in prefixes) if p]
    return [
        satellites[name]
        for norm, name in index
        if any(norm.startswith(p) for p in wanted)
    ]


def find_satellite(query: str):
    """Best single match for a name, or None.

    Preference: exact name > exact (normalised) name > name starting with the
    query > name containing the query. Ties go to the first in catalog order.
    """
    satellites, index, _groups = _snapshot()
    if query in satellites:
        return satellites[query]

    q = _normalize(query or "")
    if not q:
        return None

    for norm, name in index:
        if norm == q:
            return satellites[name]
    for norm, name in index:
        if norm.startswith(q):
            return satellites[name]
    for norm, name in index:
        if q in norm:
            return satellites[name]
    return None


def get_groups() -> dict:
    """{satellite name: group id} for the current catalog."""
    return _snapshot()[2]


def group_summary() -> list:
    """[{id, label, count}] for every group, in display order."""
    return groups.summarize(get_groups())


def select(search=None, group=None, limit=None) -> list:
    """Satellites matching a name search and/or a group. Both filters are applied
    before the limit, so a limit never hides matches that come later in the catalog."""
    satellites, index, group_of = _snapshot()
    q = _normalize(search or "")

    names = (name for norm, name in index if not q or q in norm)
    if group and group != "all":
        names = (name for name in names if group_of.get(name) == group)

    chosen = [satellites[name] for name in names]
    return chosen[:limit] if limit else chosen
