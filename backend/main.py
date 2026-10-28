import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from backend import config
from backend.satellites.african import AFRICAN_SATELLITES
from backend.services import africa
from backend.services import satellites as catalog
from backend.services import tle_service
from backend.services.magnetic import declination_deg
from backend.services.ics import passes_to_ics
from backend.services.groundtrack import get_ground_track
from backend.services.orbit_service import get_satellite_position
from backend.services.satinfo import satellite_info
from backend.services.passes import predict_passes, resolve_satellite
from backend.services.visibility import (
    MAX_PASS_HOURS,
    PASS_HOURS_AHEAD,
    compute_passes_over,
    compute_satellite_view,
    compute_visibility_cached,
)

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


def _resolve_time(at):
    """The Skyfield time for an optional ?at= timestamp (default: now).

    A timestamp without a timezone is read as UTC. Times too far from now are
    refused, because TLEs are only accurate for a few days.
    """
    now = datetime.now(timezone.utc)
    if at is None:
        return catalog.ts.from_datetime(now)
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    limit = timedelta(hours=config.MAX_TIME_TRAVEL_HOURS)
    if abs(at - now) > limit:
        raise HTTPException(
            status_code=422,
            detail=f"'at' must be within {config.MAX_TIME_TRAVEL_HOURS:g} hours of now",
        )
    return catalog.ts.from_datetime(at)


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
@app.get("/groups")
def get_groups():
    """Satellite groups (Stations, Africa, Weather ...) with how many satellites each has.

    Groups are worked out from satellite names, so treat them as a convenient
    filter rather than an authoritative catalogue.
    """
    summary = catalog.group_summary()
    return [{"id": "all", "label": "All", "count": sum(g["count"] for g in summary)}] + summary


@app.get("/positions")
def get_positions(
    search: str = Query(None, description="Case-insensitive name filter"),
    group: str = Query(None, description="Only this group (see /groups); 'all' or empty = every group"),
    limit: int = Query(100, ge=1, le=2000),
    at: datetime = Query(None, description="Show positions at this ISO time instead of now"),
    names: list[str] = Query(None, description="Exact satellite names (repeat the parameter); overrides search, group and limit"),
):
    """Position of satellites matching `search` and/or `group`, now or at time `at`.

    With no filter, African/priority satellites come first and the rest of the
    catalog fills the remaining slots, so the default view isn't just whichever
    satellites happen to be first in the CelesTrak file.
    """
    t = _resolve_time(at)
    known_groups = {g["id"] for g in catalog.group_summary()} | {"all"}
    if group and group not in known_groups:
        raise HTTPException(status_code=422, detail=f"Unknown group '{group}'")

    has_search = bool(search and search.strip())
    if names:
        catalogue = catalog.get_satellites()
        sats = [catalogue[n] for n in dict.fromkeys(names) if n in catalogue][:2000]
    elif has_search or (group and group != "all"):
        sats = catalog.select(search if has_search else None, group, limit=limit)
    else:
        priority = catalog.match_prefixes(config.PASS_WATCHLIST)
        seen = {s.name for s in priority}
        rest = (s for s in catalog.get_satellites().values() if s.name not in seen)
        sats = (priority + list(rest))[:limit]

    group_of = catalog.get_groups()
    results = []
    for sat in sats:
        pos = get_satellite_position(sat, t)
        if pos:
            entry = {"name": sat.name, "group": group_of.get(sat.name, "other"), **pos}
            if entry["group"] == "africa":
                entry["country"] = africa.country_of(sat.name)
            results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Africa
# ---------------------------------------------------------------------------
def _african_sats():
    return catalog.select(None, "africa", limit=None)


@app.get("/africa")
def africa_overview():
    """African satellites in the catalog, by country, with where they are now.

    `unmatched` lists name-table entries that match nothing in the current catalog: a typo,
    a decayed satellite, or a name CelesTrak spells differently. Use it to tune the table.
    """
    sats = _african_sats()
    rows = []
    for sat in sats:
        pos = get_satellite_position(sat)
        rows.append(
            {
                "name": sat.name,
                "country": africa.country_of(sat.name),
                "norad": sat.model.satnum,
                "lat": pos["lat"] if pos else None,
                "lon": pos["lon"] if pos else None,
                "alt_km": pos["alt_km"] if pos else None,
            }
        )
    rows.sort(key=lambda r: (r["country"] or "", r["name"]))
    counts = {}
    for r in rows:
        counts[r["country"]] = counts.get(r["country"], 0) + 1
    return {
        "satellites": rows,
        "countries": [{"country": c, "count": n} for c, n in sorted(counts.items())],
        "unmatched": africa.unmatched_entries([s.name for s in catalog.get_satellites().values()]),
    }


@app.get("/africa/passes")
def africa_passes_overhead(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    hours: int = Query(24, ge=1, le=MAX_PASS_HOURS),
):
    """Passes of every African satellite above 10 degrees from this spot, soonest first.

    Most are not visible to the eye (small cubesats, daytime): `visibility` says so, and a
    pass still matters for ground stations and radio listeners."""
    passes = compute_passes_over(_african_sats(), lat, lon, hours)
    for p in passes:
        p["country"] = africa.country_of(p["name"])
    return {"hours": hours, "passes": passes}


@app.get("/satellite/{name}")
def get_satellite(name: str):
    sat = _get_or_404(name)
    position = get_satellite_position(sat)
    if position is None:
        raise HTTPException(status_code=422, detail=f"Cannot propagate orbit for '{sat.name}'")
    return {"name": sat.name, "position": position}


@app.get("/satellite/{name}/info")
def satellite_info_endpoint(name: str):
    """Orbit facts (NORAD id, inclination, period, perigee/apogee, element age) and a short description."""
    sat = _get_or_404(name)
    info = satellite_info(sat)
    if info is None:
        raise HTTPException(status_code=422, detail=f"Cannot work out the orbit of '{sat.name}'")
    return info


@app.get("/satellite/{name}/view")
def satellite_view(
    name: str,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    hours: int = Query(PASS_HOURS_AHEAD, ge=1, le=MAX_PASS_HOURS, description="How far ahead to look for the next pass"),
):
    """Where to look for this satellite from (lat, lon) now, and its next pass.

    `look` has azimuth/elevation/distance (elevation < 0 means below the horizon),
    `above_horizon`, `status` (visible | faint | in_shadow | daylight) and `magnitude`.
    `next_pass` is the next rise-peak-set above 10 degrees, or null.
    """
    sat = _get_or_404(name)
    result = compute_satellite_view(sat, lat, lon, hours)
    if result is None:
        raise HTTPException(status_code=422, detail=f"Cannot propagate orbit for '{sat.name}'")
    return {"name": sat.name, **result}


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
    at: datetime = Query(None, description="Start the track at this ISO time instead of now"),
):
    sat = _get_or_404(satellite_name)
    t0 = _resolve_time(at)
    return {"satellite": sat.name, "track": get_ground_track(sat, minutes=minutes, step=step, t0=t0)}


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


@app.get("/passes/calendar.ics")
def passes_calendar(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    hours: int = Query(PASS_HOURS_AHEAD, ge=1, le=MAX_PASS_HOURS),
    naked_eye_only: bool = Query(True, description="Only passes visible without optical aid"),
):
    """Upcoming passes as an iCalendar file (each event has a 10-minute alarm)."""
    cached, _age = compute_visibility_cached(lat, lon, hours=hours)
    passes = [p for p in cached["next_passes"] if not naked_eye_only or p["visibility"] == "visible"]
    return Response(
        passes_to_ics(passes, lat, lon),
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="satellite-passes.ics"'},
    )


@app.get("/observer/declination")
def observer_declination(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """Magnetic declination (degrees, east positive): true bearing = compass bearing + declination."""
    return {"lat": lat, "lon": lon, "declination_deg": round(declination_deg(lat, lon), 2)}


@app.get("/observer/visibility")
def observer_visibility(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    hours: int = Query(PASS_HOURS_AHEAD, ge=1, le=MAX_PASS_HOURS, description="How far ahead to look for passes"),
    naked_eye_only: bool = Query(
        False,
        description="Only satellites (and passes) that can be seen without optical aid: "
        "dark sky, sunlit and bright enough",
    ),
):
    """What the observer can see.

    `visible_now` lists every satellite above the horizon. Each has `status`:
    visible | faint | in_shadow | daylight, plus `sunlit`, an estimated `magnitude`
    (only for objects with a known brightness) and per-second `*_rate` fields for
    smooth client-side animation. `observer` says how dark the sky is.
    """
    cached, age = compute_visibility_cached(lat, lon, hours=hours)
    # age_seconds: how old the computation is (up to VISIBILITY_CACHE_SECONDS). A client
    # adds it to its own elapsed time when it moves satellites along their rates.
    result = {**cached, "age_seconds": round(age, 2)}
    if not naked_eye_only:
        return result

    return {
        **result,
        "visible_now": [s for s in result["visible_now"] if s["naked_eye"]],
        "next_passes": [p for p in result["next_passes"] if p["visibility"] == "visible"],
    }
