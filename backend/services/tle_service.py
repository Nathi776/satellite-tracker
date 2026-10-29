"""Fetch, cache and refresh TLE data.

Behaviour:
  * data is downloaded from CelesTrak and reused until it is older than TLE_TTL_SECONDS
  * every successful download is also written to disk
  * if a refresh fails we keep serving the stale in-memory data, and if there is
    nothing in memory we fall back to the last copy saved on disk
  * with the background refresher running (services/refresher.py) requests never download:
    they use whatever is in memory, and the refresher swaps in new data when it is ready
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone

import requests

from backend import config

log = logging.getLogger(__name__)

_lock = threading.RLock()
_state = {
    "data": {},            # name -> {"name", "line1", "line2", "norad_id"}
    "last_updated": None,  # timezone-aware datetime of the last successful download
    "source": None,        # "network" | "disk"
    "version": 0,          # bumped whenever data changes (lets other caches invalidate)
    "last_failure": None,  # time.monotonic() of the last failed refresh
    "background": False,   # True while the background refresher owns the downloads
    "refreshing": False,   # a background download is in progress right now
    "last_error": None,    # message of the last failed background refresh
}
_ready = threading.Event()  # set once any data is in memory

# After a failed refresh, don't hammer CelesTrak (or block requests on its
# timeout) again for this many seconds.
RETRY_BACKOFF_SECONDS = 60


class TLEUnavailable(RuntimeError):
    """No TLE data in memory, and neither CelesTrak nor the disk cache could provide any."""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def parse_tle_text(text: str) -> dict:
    """Parse 3-line TLE text (name / line 1 / line 2) into a dict keyed by name."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    result = {}
    i = 0
    while i + 2 < len(lines):
        name = lines[i].strip()
        line1 = lines[i + 1].strip()
        line2 = lines[i + 2].strip()

        if line1.startswith("1 ") and line2.startswith("2 "):
            norad_id = line1[2:7].strip()
            key = name
            if key in result:  # a handful of objects share a name; keep both
                key = f"{name} ({norad_id})"
            result[key] = {
                "name": key,
                "line1": line1,
                "line2": line2,
                "norad_id": norad_id,
            }
            i += 3
        else:
            i += 1  # misaligned input: resync instead of dropping the rest of the file
    return result


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------
def _save_to_disk(data: dict, fetched_at: datetime) -> None:
    try:
        path = config.TLE_CACHE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"fetched_at": fetched_at.isoformat(), "data": data}),
            encoding="utf-8",
        )
        tmp.replace(path)  # atomic: never leaves a half-written cache behind
    except Exception as exc:  # caching is best-effort
        log.warning("Could not write TLE cache: %s", exc)


def _load_from_disk():
    path = config.TLE_CACHE_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        data = payload["data"]
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        return (data, fetched_at) if data else None
    except Exception as exc:
        log.warning("Ignoring unreadable TLE cache %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
def _download() -> str:
    response = requests.get(
        config.CELESTRAK_URL,
        timeout=config.TLE_FETCH_TIMEOUT,
        headers={"User-Agent": "african-satellite-tracker/0.1"},
    )
    response.raise_for_status()
    return response.text


def _install(data: dict, fetched_at: datetime, source: str) -> None:
    _state["data"] = data
    _state["last_updated"] = fetched_at
    _state["source"] = source
    _state["version"] += 1
    _ready.set()


def set_background(on: bool) -> None:
    """Tell get_tles() whether a background refresher is keeping the data fresh."""
    with _lock:
        _state["background"] = on


def load_cached() -> bool:
    """Put the last copy saved on disk into memory (no network). False if there is none."""
    cached = _load_from_disk()
    if not cached:
        return False
    data, fetched_at = cached
    with _lock:
        if not _state["data"]:
            _install(data, fetched_at, "disk")
    return True


def refresh_in_background() -> dict:
    """Download fresh TLEs without holding the lock; requests keep using the old data meanwhile."""
    _state["refreshing"] = True
    try:
        data = fetch_tles()
        _state["last_error"] = None
        return data
    except Exception as exc:
        _state["last_error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        _state["refreshing"] = False


def seconds_until_stale():
    """Seconds until the data passes its TTL (0 when already stale, None with no data)."""
    age = _age_seconds()
    return None if age is None else max(0.0, config.TLE_TTL_SECONDS - age)


def fetch_tles() -> dict:
    """Download fresh TLEs now. Raises on network errors or an empty/invalid response."""
    log.info("Fetching TLEs from CelesTrak...")
    data = parse_tle_text(_download())
    if not data:
        raise ValueError("CelesTrak response contained no valid TLEs")

    fetched_at = datetime.now(timezone.utc)
    with _lock:
        _install(data, fetched_at, "network")
    _save_to_disk(data, fetched_at)
    log.info("Loaded %d satellites from CelesTrak", len(data))
    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _age_seconds():
    updated = _state["last_updated"]
    if updated is None:
        return None
    return (datetime.now(timezone.utc) - updated).total_seconds()


def get_tles(force_refresh: bool = False) -> dict:
    """Return the TLE dict, refreshing it when it is older than the TTL.

    While the background refresher runs, data that is already in memory is returned as it
    is, however old: the refresher is responsible for replacing it."""
    if _state["background"] and not force_refresh:
        if not _state["data"]:
            # first start: give the refresher a moment to load the disk copy or download
            _ready.wait(config.TLE_FETCH_TIMEOUT + 5)
        if _state["data"]:
            return _state["data"]
    with _lock:
        age = _age_seconds()
        fresh = age is not None and age < config.TLE_TTL_SECONDS
        if fresh and not force_refresh:
            return _state["data"]

        last_failure = _state["last_failure"]
        backing_off = (
            last_failure is not None
            and time.monotonic() - last_failure < RETRY_BACKOFF_SECONDS
            and not force_refresh
        )

        if not backing_off:
            try:
                data = fetch_tles()
                _state["last_failure"] = None
                return data
            except Exception as exc:
                _state["last_failure"] = time.monotonic()
                log.warning("TLE refresh failed: %s", exc)

        if _state["data"]:  # keep serving stale data rather than failing
            return _state["data"]

        cached = _load_from_disk()
        if cached:
            data, fetched_at = cached
            _install(data, fetched_at, "disk")
            log.warning("Using TLE data from disk cache (fetched %s)", fetched_at)
            return data

        raise TLEUnavailable(
            "No TLE data available: CelesTrak could not be reached and there is no disk cache yet."
        )


def get_tle_status() -> dict:
    """Metadata for /health. Never triggers a download."""
    with _lock:
        updated = _state["last_updated"]
        age = _age_seconds()
        return {
            "loaded": bool(_state["data"]),
            "satellites": len(_state["data"]),
            "source": _state["source"],
            "last_updated": updated.isoformat() if updated else None,
            "age_seconds": round(age) if age is not None else None,
            "ttl_seconds": config.TLE_TTL_SECONDS,
            "background_refresh": _state["background"],
            "refreshing": _state["refreshing"],
            "next_refresh_in_seconds": (
                round(seconds_until_stale()) if _state["background"] and age is not None else None
            ),
            "last_error": _state["last_error"],
        }


def get_version() -> int:
    return _state["version"]


def reset_for_tests() -> None:
    with _lock:
        _state.update(
            data={},
            last_updated=None,
            source=None,
            last_failure=None,
            background=False,
            refreshing=False,
            last_error=None,
            version=_state["version"] + 1,
        )
        _ready.clear()
