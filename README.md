# 🛰 African Satellite Tracker

Live satellite tracking with a focus on Africa: see where satellites are right now,
which ones are above your horizon, and when they will next pass over you.

- **Backend:** FastAPI + Skyfield (orbit maths from CelesTrak TLEs)
- **Frontend:** React + TypeScript + Leaflet (Vite)

## Run it locally

**Backend** (from the repo root)

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r backend/requirements-dev.txt
uvicorn backend.main:app --reload
```

The API is then on http://127.0.0.1:8000 (interactive docs at `/docs`).

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

If the API is not on `http://127.0.0.1:8000`, copy `frontend/.env.example` to
`frontend/.env.local` and set `VITE_API_URL`.

**Tests**

```bash
python -m pytest backend/tests
```

The tests run offline against a TLE fixture, so they don't need internet access.

## API

| Endpoint | What it returns |
|---|---|
| `GET /health` | Status and how fresh the TLE data is |
| `GET /groups` | Catalog groups (Stations, Africa, Weather, Navigation, Starlink, OneWeb, Comms, Other) with counts |
| `GET /positions?search=&group=&limit=&at=` | Position, altitude, speed, period and footprint radius of matching satellites. `group` filters before `limit` (max 2000); `at` (ISO time, naive = UTC) shows any moment within ±48 h, else `422` |
| `GET /satellite/{name}` | One satellite's current position |
| `GET /iss` | The ISS's current position |
| `GET /groundtrack/{name}?minutes=&step=&at=` | Ground track starting now, or at `at` |
| `GET /observer/visibility?lat=&lon=&hours=&naked_eye_only=` | Your sky: how dark it is, every satellite above your horizon (elevation, azimuth, range, sunlit?, estimated magnitude, per-second motion rates) and upcoming passes (up to 72 h) classified as `visible`, `faint`, `in_shadow` or `daylight` |
| `GET /passes/iss?lat=&lon=` | ISS passes over a location |
| `GET /passes/african/{name}?lat=&lon=` | Passes of a named satellite (defaults to Pretoria) |

Name matching ignores case, spaces and punctuation (`zacube 1` finds `ZACUBE-1`).
Unknown satellites return `404`; invalid coordinates return `422`.

## Groups, time travel and footprints

Groups come from satellite **names** (e.g. `STARLINK-…`, `NOAA …`, `GPS …`), so they are a
good heuristic, not an official classification. "Africa" matches the name tokens in
`AFRICA_NAME_TOKENS` (`backend/config.py`). Time travel is limited to `MAX_TIME_TRAVEL_HOURS`
(default 48); orbits get less accurate the further from the TLE epoch. The footprint circle is the
area from which the satellite is above the horizon.

## How the data works

TLEs are downloaded from CelesTrak, cached in memory, and saved to
`backend/data/tle_cache.json`. They refresh every 6 hours. If CelesTrak is
unreachable, the API keeps serving the last data it has, including after a restart.

## What "visible" means

A satellite is reported as visible to the naked eye only when **all** of these hold:

1. **Dark sky:** the Sun is more than 6° below your horizon (end of civil twilight).
2. **Sunlit:** the satellite is not inside Earth's shadow (checked with Skyfield and the `de421.bsp` ephemeris).
3. **Bright enough:** its estimated apparent magnitude is at or below `NAKED_EYE_LIMIT_MAG`, and it is more than 10° above the horizon.

TLEs say nothing about a satellite's size or brightness, so (3) can only be estimated for objects
listed in `BRIGHT_STD_MAGS` in `backend/config.py` (ISS, Tiangong and Hubble for now). Every other
satellite is shown as *Too faint* when it is sunlit on a dark sky, never as visible. The listed
magnitudes are approximate: refine them with McCants' `qs.mag` or Heavens-Above values.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `TLE_TTL_SECONDS` | `21600` | How long TLEs are reused before refreshing |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins. Set this when you deploy |
| `VISIBILITY_CACHE_SECONDS` | `5` | How long a visibility result is reused |
| `CELESTRAK_URL` | active satellites | TLE source |
| `DARK_SKY_SUN_ALTITUDE_DEG` | `-6` | Sun must be below this for the sky to count as dark |
| `MAX_TIME_TRAVEL_HOURS` | `48` | How far from now `at=` may reach |
| `NAKED_EYE_LIMIT_MAG` | `4.5` | Faintest magnitude treated as visible (~5.5 dark site, ~4 in a suburb) |

## Roadmap

- Marker clustering was skipped on purpose (it fights moving satellites; a canvas layer is used instead)
- 3D globe, phone-orientation AR, pass alerts
- Brightness data for more satellites (beyond ISS, Tiangong and Hubble)
