"""The shared satellite catalog.

EarthSatellite objects are built once per TLE refresh and reused by every
endpoint, instead of being rebuilt from raw TLE text on each request.
"""
import gc
import logging
import re
import threading
import time

from skyfield.api import EarthSatellite, load

from backend.services import groups, tle_service

log = logging.getLogger(__name__)

# One timescale for the whole app.
ts = load.timescale()

_BATCH = 200
_YIELD_SECONDS = 0.003

_lock = threading.Lock()        # guards _cache (held only for the swap)
_build_lock = threading.Lock()  # one catalogue build at a time
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


def _build(tles: dict):
    satellites = build_satellites(tles)
    index = [(_normalize(name), name) for name in satellites]
    # Classify in small batches and pause between them: this runs on the refresher thread
    # while requests are being served, and without the pauses it would take most of the CPU.
    group_by_name = {}
    names = list(satellites)
    for start in range(0, len(names), _BATCH):
        group_by_name.update(groups.classify_all(names[start : start + _BATCH]))
        time.sleep(_YIELD_SECONDS)
    return satellites, index, group_by_name


def _build_and_publish(tles: dict, version: int):
    """Build outside the readers' lock, then swap the new snapshot in as one step."""
    with _build_lock:
        if _cache["version"] == version:  # someone else just built it
            return _cache["snapshot"]
        # Building tens of thousands of objects makes Python's cycle collector rescan the
        # whole heap again and again, which pauses every request thread for a second or so.
        # Pause it for the build; afterwards freeze what exists so later scans skip it.
        gc_was_on = gc.isenabled()
        gc.disable()
        try:
            snapshot = _build(tles)
            sats = list(snapshot[0].values())
            if sats:
                # also build the vectorised SGP4 array now, not during the first request
                from backend.services import prefilter

                prefilter.warm(sats)
        finally:
            if gc_was_on:
                gc.enable()
        with _lock:
            _cache["snapshot"] = snapshot
            _cache["version"] = version
        gc.freeze()
        log.info("Built %d EarthSatellite objects", len(snapshot[0]))
        return snapshot


def warm() -> bool:
    """Bring the catalogue up to date with the TLE data in memory. True if it rebuilt."""
    tles = tle_service.get_tles()
    version = tle_service.get_version()
    if _cache["version"] == version:
        return False
    _build_and_publish(tles, version)
    return True


def get_version():
    """Version of the catalogue being served (changes when a new one is swapped in)."""
    return _cache["version"]


def _snapshot():
    tles = tle_service.get_tles()  # may refresh; raises TLEUnavailable if nothing is available
    version = tle_service.get_version()

    if _cache["version"] == version:
        return _cache["snapshot"]
    if _cache["snapshot"][0] and tle_service._state["background"]:
        # newer data is being prepared: keep serving the current catalogue until it is ready
        return _cache["snapshot"]
    return _build_and_publish(tles, version)


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


def group_ids(group) -> list:
    """'stations,weather' (or a list) -> ['stations', 'weather']; 'all' or empty -> []."""
    if not group:
        return []
    parts = group.split(",") if isinstance(group, str) else list(group)
    ids = [p.strip() for p in parts if p and p.strip()]
    return [] if "all" in ids else list(dict.fromkeys(ids))


def _fair_shares(sizes: dict, limit: int) -> dict:
    """Split `limit` slots between groups: small groups get all they have, the rest is shared
    equally. Otherwise one big group (Communications, 1,800 satellites) would fill every slot."""
    shares, remaining = {}, limit
    left = sorted(sizes, key=lambda g: sizes[g])
    for i, gid in enumerate(left):
        share = min(sizes[gid], remaining // (len(left) - i))
        shares[gid] = share
        remaining -= share
    return shares


def select(search=None, group=None, limit=None) -> list:
    """Satellites matching a name search and/or one or more groups (a list, or a comma
    separated string). Both filters are applied before the limit, so a limit never hides
    matches that come later in the catalog; with several groups the limit is shared fairly."""
    satellites, index, group_of = _snapshot()
    q = _normalize(search or "")
    wanted = group_ids(group)

    names = [name for norm, name in index if not q or q in norm]
    if wanted:
        picked = {g: [] for g in wanted}
        for name in names:
            gid = group_of.get(name)
            if gid in picked:
                picked[gid].append(name)
        if limit and len(wanted) > 1:
            shares = _fair_shares({g: len(v) for g, v in picked.items()}, limit)
            picked = {g: v[: shares[g]] for g, v in picked.items()}
        keep = {n for v in picked.values() for n in v}
        names = [n for n in names if n in keep]  # back to catalogue order

    chosen = [satellites[name] for name in names]
    return chosen[:limit] if limit else chosen
