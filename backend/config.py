"""Central configuration. Everything here can be overridden with environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- TLE source -------------------------------------------------------------
CELESTRAK_URL = os.getenv(
    "CELESTRAK_URL",
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
)

# CelesTrak updates its data roughly every 2 hours and asks clients not to poll
# more often than that. 6 hours keeps us polite and the data fresh enough.
TLE_TTL_SECONDS = int(os.getenv("TLE_TTL_SECONDS", str(6 * 3600)))
TLE_FETCH_TIMEOUT = int(os.getenv("TLE_FETCH_TIMEOUT", "20"))

# Download new orbit data (and rebuild the catalogue) in a background thread, so that no request
# has to wait for it. Set to 0 to fall back to refreshing on the first request after the TTL.
REFRESH_IN_BACKGROUND = os.getenv("REFRESH_IN_BACKGROUND", "1") not in ("0", "false", "False", "")

# Last good download is stored here so the API still starts when CelesTrak is down.
TLE_CACHE_PATH = Path(os.getenv("TLE_CACHE_PATH", BASE_DIR / "data" / "tle_cache.json"))

# --- Observer ---------------------------------------------------------------
# Used by endpoints that need an observer when the caller doesn't send one.
DEFAULT_OBSERVER = {
    "name": "Pretoria",
    "lat": -25.7479,
    "lon": 28.2293,
    "elevation_m": 1350.0,
}

# McCants' brightness catalogue (see backend/services/quicksat.py). Hand-entered figures in
# BRIGHT_STD_MAGS above take priority. Set to a missing path to turn this off.
QUICKSAT_MAG_PATH = os.getenv(
    "QUICKSAT_MAG_PATH", str(Path(__file__).parent / "resources" / "quicksat.mag")
)

# --- Satellite groups -------------------------------------------------------
# Extra "Africa" name prefixes as (prefix, country) pairs, on top of the table in
# backend/services/africa.py. The TLE data has no operator field, so this is name matching.
EXTRA_ENTRIES: list[tuple[str, str]] = []

# --- Time travel ------------------------------------------------------------
# How far from "now" /positions?at= and /groundtrack?at= will go. TLEs are only
# accurate for a few days, so going further would show nonsense.
MAX_TIME_TRAVEL_HOURS = float(os.getenv("MAX_TIME_TRAVEL_HOURS", "48"))

# --- Naked-eye visibility ---------------------------------------------------
# A satellite can be seen without optical aid when (1) the observer's sky is dark
# enough, (2) the satellite is in sunlight and (3) it is bright enough.
#
# (1) Sun altitude below this many degrees. -6 is the end of civil twilight, when
#     the brightest satellites become easy to spot.
DARK_SKY_SUN_ALTITUDE_DEG = float(os.getenv("DARK_SKY_SUN_ALTITUDE_DEG", "-6"))
# (3) Apparent magnitude at or below this is treated as visible to the naked eye
#     (lower = brighter; ~5.5 is the limit under a good dark sky, ~4 from a suburb).
NAKED_EYE_LIMIT_MAG = float(os.getenv("NAKED_EYE_LIMIT_MAG", "4.5"))

# Standard (intrinsic) magnitude: how bright the object would look at 1000 km range,
# half illuminated. TLEs contain no size or brightness, so apparent magnitude can only
# be estimated for objects listed here. These are approximate figures; adjust them
# if you have better data (e.g. McCants' qs.mag file or Heavens-Above values).
# Objects that are not listed are never reported as naked-eye visible.
BRIGHT_STD_MAGS = {
    "ISS (ZARYA)": -1.8,
    "CSS (TIANHE)": -1.0,
    "HST": 2.2,
}

# How far from "now" the `at` query parameter may reach. TLEs are only accurate for a
# few days, so beyond this the positions would be fiction.
MAX_TIME_OFFSET_HOURS = float(os.getenv("MAX_TIME_OFFSET_HOURS", "72"))

# --- API --------------------------------------------------------------------
# Comma separated list, e.g. "https://my-app.vercel.app,http://localhost:5173".
# Defaults to "*" so local development just works; restrict it when you deploy.
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]

# How long a computed /observer/visibility answer is reused (seconds).
VISIBILITY_CACHE_SECONDS = float(os.getenv("VISIBILITY_CACHE_SECONDS", "5"))

# --- Pass prediction --------------------------------------------------------
# find_events() costs ~1-2 ms per satellite, so pass prediction runs on a
# watchlist instead of all ~10,000 active satellites. Names are matched loosely
# (case, spaces and punctuation are ignored). Phase 1 replaces this with a
# proper "visible to the naked eye" filter.
PASS_WATCHLIST = [
    "ISS (ZARYA)",
    "CSS (TIANHE)",
    "HST",
    "ZACUBE",
    "NIGERIASAT",
    "EGYPTSAT",
    "MISRSAT",
    "ETHIOPIA",
    "RASCOM",
    "GHANASAT",
    "MOROCCO",
    "MOHAMMED VI",
    "ANGOSAT",
    "KENYA",
    "SUMBANDILA",
]
