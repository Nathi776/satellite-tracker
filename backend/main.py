import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend import config
from backend.satellites.african import AFRICAN_SATELLITES
from backend.services import satellites as catalog
from backend.services import tle_service
from backend.services.groundtrack import get_ground_track
from backend.services.orbit_service import get_satellite_position
from backend.services.passes import predict_passes, resolve_satellite
from backend.services.visibility import compute_visibility_cached

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("satellite-tracker")


def _warm_up():
    """Download TLEs and build the catalog in the background so the first request is fast."""
    try:
        catalog.get_satellites()
    except Exception as exc:
        log.warning("Startup warm-up failed (will retry on first request): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(title="African Satellite Tracker", lifespan=lifespan)

# "*" together with credentials is rejected by browsers, and this API uses no cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(tle_service.TLEUnavailable)
async def tle_unavailable_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def _get_or_404(name: str):
    sat = resolve_satellite(name)
    if sat is None:
        raise HTTPException(status_code=404, detail=f"Satellite '{name}' not found")
    return sat


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Satellite Tracker API is running."}


@app.get("/health")
def health():
    """Cheap status check. Never triggers a download."""
    return {"status": "ok", "tle": tle_service.get_tle_status()}


# ---------------------------------------------------------------------------
# Satellites
# ---------------------------------------------------------------------------
@app.get("/positions")
def get_positions(
    search: str = Query(None, description="Case-insensitive name filter"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Current position of satellites matching `search`.

    With no search, African/priority satellites come first and the rest of the
    catalog fills the remaining slots, so the default view isn't just whichever
    satellites happen to be first in the CelesTrak file.
    """
    if search and search.strip():
        sats = catalog.search_satellites(search, limit=limit)
    else:
        priority = catalog.match_prefixes(config.PASS_WATCHLIST)
        seen = {s.name for s in priority}
        rest = (s for s in catalog.get_satellites().values() if s.name not in seen)
        sats = (priority + list(rest))[:limit]

    t = catalog.ts.now()
    results = []
    for sat in sats:
        pos = get_satellite_position(sat, t)
        if pos:
            results.append({"name": sat.name, **pos})
    return results


@app.get("/satellite/{name}")
def get_satellite(name: str):
    sat = _get_or_404(name)
    position = get_satellite_position(sat)
    if position is None:
        raise HTTPException(status_code=422, detail=f"Cannot propagate orbit for '{sat.name}'")
    return {"name": sat.name, "position": position}


@app.get("/iss")
def iss_position():
    sat = _get_or_404("ISS")
    position = get_satellite_position(sat)
    if position is None:
        raise HTTPException(status_code=422, detail="Cannot propagate the ISS orbit")
    return {"name": sat.name, **position}


@app.get("/groundtrack/{satellite_name}")
def ground_track(
    satellite_name: str,
    minutes: int = Query(90, ge=1, le=1440),
    step: float = Query(2, gt=0, le=30),
):
    sat = _get_or_404(satellite_name)
    return {"satellite": sat.name, "track": get_ground_track(sat, minutes=minutes, step=step)}


# ---------------------------------------------------------------------------
# Passes
# ---------------------------------------------------------------------------
@app.get("/passes/iss")
def iss_passes(
    lat: float = Query(None, ge=-90, le=90),
    lon: float = Query(None, ge=-180, le=180),
):
    return predict_passes("ISS", lat, lon)


@app.get("/passes/african/{satellite_name}")
def african_passes(
    satellite_name: str,
    lat: float = Query(None, ge=-90, le=90),
    lon: float = Query(None, ge=-180, le=180),
):
    result = predict_passes(satellite_name, lat, lon)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Satellite '{satellite_name}' not found")
    result["country"] = AFRICAN_SATELLITES.get(result["satellite"], {}).get("country")
    return result


@app.get("/observer/visibility")
def observer_visibility(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    visible, passes = compute_visibility_cached(lat, lon)
    return {
        "observer": {"lat": lat, "lon": lon},
        "visible_now": visible,
        "next_passes": passes,
    }
