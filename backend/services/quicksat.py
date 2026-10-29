"""Brightness figures from Mike McCants' `quicksat.mag` (a.k.a. qs.mag).

The file lists an *intrinsic magnitude* per NORAD number: the maximum apparent brightness of the
object seen at full phase from 1000 km (QuickSat documentation, "Description of the Intrinsic
Magnitudes File"). Our magnitude model (`sky.estimate_magnitude`) expects a *standard magnitude*:
brightness at 1000 km with the object half lit (phase angle 90 degrees). A sphere that is fully
lit is 2.5*log10(pi) = 1.24 magnitudes brighter than at half phase, so
standard = intrinsic + 1.24.

Limits worth knowing: the file is old (QuickSat dates from 1990 and the catalogue stops
at NORAD 36511, so new satellites such as Starlink are not in it), tumbling objects are fainter
than their "maximum", and sizes are partly guessed. Treat results as optimistic estimates.

Fixed-width layout (1-based columns): 1-5 NORAD number, 7 flag, 19-32 name, 34-37 magnitude.
"""
import math
import threading
from pathlib import Path

from backend import config

INTRINSIC_TO_STANDARD = 2.5 * math.log10(math.pi)  # ~1.24

# Flags: d decayed, h high orbit, g geosynchronous/other - never visible as moving objects here.
# f, t: tumbling, so the "maximum" is a poor guide to what you will see.
SKIPPED_FLAGS = set("dhgft")

_lock = threading.Lock()
_loaded: dict[int, tuple[float, str]] | None = None


def parse(text: str) -> dict[int, tuple[float, str]]:
    """{norad_id: (intrinsic_magnitude, name)} for every usable row."""
    table: dict[int, tuple[float, str]] = {}
    for line in text.splitlines():
        if not line[:5].strip().isdigit():
            continue
        norad = int(line[:5])
        if norad >= 99999:  # the file ends with a header-like sentinel row
            continue
        if line[6:7] in SKIPPED_FLAGS:
            continue
        try:
            mag = float(line[33:37])
        except ValueError:
            continue  # no magnitude on this row (size only)
        table[norad] = (mag, line[18:32].strip())
    return table


def parse_rcs(text: str) -> dict[int, tuple[float, float]]:
    """{norad_id: (intrinsic_magnitude, rcs_m2)} for usable rows that also list an RCS
    (columns 50-56). Used to fit the size-to-brightness line in satcat.py, not at run time."""
    out: dict[int, tuple[float, float]] = {}
    for line in text.splitlines():
        if not line[:5].strip().isdigit() or int(line[:5]) >= 99999 or line[6:7] in SKIPPED_FLAGS:
            continue
        try:
            mag = float(line[33:37])
            rcs = float(line[49:56])
        except ValueError:
            continue
        if rcs > 0:
            out[int(line[:5])] = (mag, rcs)
    return out


def _load() -> dict[int, tuple[float, str]]:
    path = Path(config.QUICKSAT_MAG_PATH)
    try:
        return parse(path.read_text(encoding="latin-1"))
    except OSError:
        return {}


def table() -> dict[int, tuple[float, str]]:
    global _loaded
    with _lock:
        if _loaded is None:
            _loaded = _load()
        return _loaded


def reset_for_tests() -> None:
    global _loaded
    with _lock:
        _loaded = None


def standard_magnitude(norad: int | None):
    """Standard magnitude (see module docstring) for a NORAD number, or None if unknown."""
    if norad is None:
        return None
    row = table().get(int(norad))
    return None if row is None else row[0] + INTRINSIC_TO_STANDARD
