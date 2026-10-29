"""Keeps the orbit data fresh without ever making a request wait for it.

Without this, the first request after the data's TTL ran out downloaded the new TLE file
itself (up to the fetch timeout) and the next one rebuilt the whole catalogue (about three
seconds for the public catalogue). Here a single background thread does both: it downloads,
builds the new catalogue next to the old one, and swaps it in as one step. Requests keep
using the old data until then.

Failures are retried with growing pauses (1, 2, 4 ... up to 30 minutes); meanwhile the old
data keeps being served, and /health shows the last error.
"""
import logging
import threading

from backend import config
from backend.services import satellites as catalog
from backend.services import satcat, tle_service

log = logging.getLogger(__name__)

RETRY_BASE_SECONDS = 60
RETRY_MAX_SECONDS = 30 * 60

_thread = None
_stop = threading.Event()


def _retry_delay(failures: int) -> float:
    return min(RETRY_BASE_SECONDS * 2 ** (failures - 1), RETRY_MAX_SECONDS)


def refresh_once() -> bool:
    """One refresh: download, then build the catalogue. Raises if the download fails."""
    tle_service.refresh_in_background()
    catalog.warm()
    return True


def _startup() -> None:
    """Get something usable into memory as fast as possible: the disk copy if there is one."""
    try:
        if not tle_service.load_cached():
            tle_service.refresh_in_background()
        catalog.warm()
    except Exception as exc:
        log.warning("Startup load failed, will retry: %s", exc)


def _refresh_satcat() -> None:
    """Weekly, and never allowed to disturb the orbit data refresh."""
    try:
        satcat.refresh_if_stale()
    except Exception as exc:
        log.warning("SATCAT refresh failed: %s", exc)


def _run(stop: threading.Event) -> None:
    _startup()
    _refresh_satcat()
    failures = 0
    while True:
        wait = tle_service.seconds_until_stale()
        if wait is None:  # still nothing loaded
            wait = 0
        if failures:
            wait = max(wait, _retry_delay(failures))
        if stop.wait(wait):
            return
        if tle_service.seconds_until_stale() not in (0, 0.0, None):
            continue  # data was refreshed by someone else in the meantime
        _refresh_satcat()
        try:
            refresh_once()
            failures = 0
        except Exception as exc:
            failures += 1
            log.warning(
                "Background TLE refresh failed (%s); keeping the current data, retrying in %ds",
                exc,
                _retry_delay(failures),
            )


def start() -> None:
    """Start the refresher (once). It is a daemon thread, so it never blocks shutdown."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    tle_service.set_background(True)
    _thread = threading.Thread(target=_run, args=(_stop,), name="tle-refresher", daemon=True)
    _thread.start()


def stop() -> None:
    global _thread
    _stop.set()
    tle_service.set_background(False)
    if _thread is not None:
        _thread.join(timeout=5)
    _thread = None
