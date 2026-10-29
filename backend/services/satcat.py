"""Brightness estimates from object size, for satellites that no brightness catalogue covers.

McCants' quicksat.mag (see quicksat.py) stops at NORAD 36511 (2010), so Starlink, OneWeb and every
other recent launch have no figure. CelesTrak's SATCAT lists a radar cross-section (RCS, in m²) for
most objects, and size is what mostly decides how bright something is. We fit a line through the
objects that are in *both* data sets (the quicksat.mag rows also carry an RCS column):

    standard magnitude  =  STD_MAG_AT_1M2  -  STD_MAG_PER_DECADE * log10(RCS in m²)

The fit is made by `tests/test_satcat.py` from the file in the repo, which checks these constants
still match it. For ~1,100 objects the scatter around the line is about 0.9 magnitudes (shape,
panels and paint matter as much as area), so a figure from here is a rough guide, not a
measurement. Callers keep it apart from real figures (`source == "size"`) and require extra
brightness before calling an object visible to the naked eye.

The SATCAT is downloaded at most once a week, kept on disk, and a failed download is ignored: the
app then simply has no size-based figures.
"""
import csv
import io
import json
import logging
import math
import threading
import time
from pathlib import Path

import requests

from backend import config

log = logging.getLogger(__name__)

# Least-squares fit of quicksat.mag standard magnitudes (intrinsic + 1.24) against log10(RCS).
STD_MAG_AT_1M2 = 7.9
STD_MAG_PER_DECADE = 2.8

# Size-based figures are uncertain by ~0.9 mag; make them fainter by this much before they can
# count as "visible to the naked eye", so that a lucky estimate does not promise a sighting.
NAKED_EYE_MARGIN_MAG = 0.5

# Below this RCS the object is too small to matter (and the fit has almost no data there).
MIN_RCS_M2 = 0.05

_lock = threading.Lock()
_loaded = None  # {norad: rcs_m2}
_fetched_at = None  # epoch seconds of the data in memory


def parse_csv(text: str) -> dict:
    """{norad_id: rcs_m2} from a CelesTrak SATCAT CSV. Columns are found by name."""
    table = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            norad = int(row["NORAD_CAT_ID"])
            rcs = float((row.get("RCS") or "").strip())
        except (KeyError, ValueError):
            continue
        if rcs > 0:
            table[norad] = rcs
    return table


def std_mag_from_rcs(rcs_m2: float) -> float:
    return STD_MAG_AT_1M2 - STD_MAG_PER_DECADE * math.log10(max(rcs_m2, MIN_RCS_M2))


# ---------------------------------------------------------------------------
# Loading and refreshing
# ---------------------------------------------------------------------------
def _cache_path() -> Path:
    return Path(config.SATCAT_CACHE_PATH)


def _load_disk():
    path = _cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {int(k): float(v) for k, v in payload["rcs"].items()}, float(payload["fetched_at"])
    except Exception:
        return None


def _save_disk(table: dict, fetched_at: float) -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": fetched_at, "rcs": table}), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        log.warning("Could not write SATCAT cache: %s", exc)


def _download() -> str:
    response = requests.get(
        config.SATCAT_URL,
        timeout=config.TLE_FETCH_TIMEOUT,
        headers={"User-Agent": "african-satellite-tracker/0.1"},
    )
    response.raise_for_status()
    return response.text


def table() -> dict:
    """{norad: rcs_m2}; from memory, else from disk, else empty. Never touches the network."""
    global _loaded, _fetched_at
    with _lock:
        if _loaded is None:
            cached = _load_disk()
            _loaded, _fetched_at = cached if cached else ({}, None)
        return _loaded


def refresh_if_stale(now=None) -> bool:
    """Download the SATCAT if our copy is missing or older than SATCAT_TTL_SECONDS.

    True if new data was installed. Network errors are logged and swallowed."""
    global _loaded, _fetched_at
    table()  # make sure the disk copy is considered
    now = time.time() if now is None else now
    if _fetched_at is not None and now - _fetched_at < config.SATCAT_TTL_SECONDS:
        return False
    if not config.SATCAT_URL:
        return False
    try:
        data = parse_csv(_download())
        if not data:
            raise ValueError("no usable rows in the SATCAT response")
    except Exception as exc:
        log.warning("SATCAT refresh failed (size-based brightness stays as it is): %s", exc)
        return False
    with _lock:
        _loaded, _fetched_at = data, now
    _save_disk(data, now)
    log.info("Loaded RCS for %d objects from the SATCAT", len(data))
    return True


def standard_magnitude(norad):
    """Standard magnitude estimated from the object's RCS, or None if the SATCAT has no size."""
    if norad is None:
        return None
    rcs = table().get(int(norad))
    return None if rcs is None else std_mag_from_rcs(rcs)


def reset_for_tests() -> None:
    global _loaded, _fetched_at
    with _lock:
        _loaded, _fetched_at = None, None
