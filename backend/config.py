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
