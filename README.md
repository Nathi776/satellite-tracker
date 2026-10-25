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
| `GET /positions?search=&limit=` | Current position, altitude, speed and period of matching satellites |
| `GET /satellite/{name}` | One satellite's current position |
| `GET /iss` | The ISS's current position |
| `GET /groundtrack/{name}?minutes=&step=` | Future ground track |
| `GET /observer/visibility?lat=&lon=` | Satellites above your horizon (with elevation, azimuth, range) and upcoming passes |
| `GET /passes/iss?lat=&lon=` | ISS passes over a location |
| `GET /passes/african/{name}?lat=&lon=` | Passes of a named satellite (defaults to Pretoria) |

Name matching ignores case, spaces and punctuation (`zacube 1` finds `ZACUBE-1`).
Unknown satellites return `404`; invalid coordinates return `422`.

## How the data works

TLEs are downloaded from CelesTrak, cached in memory, and saved to
`backend/data/tle_cache.json`. They refresh every 6 hours. If CelesTrak is
unreachable, the API keeps serving the last data it has, including after a restart.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `TLE_TTL_SECONDS` | `21600` | How long TLEs are reused before refreshing |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins. Set this when you deploy |
| `VISIBILITY_CACHE_SECONDS` | `5` | How long a visibility result is reused |
| `CELESTRAK_URL` | active satellites | TLE source |

## Roadmap

- Naked-eye visibility (observer in darkness and satellite sunlit)
- Sky radar view and live updates
- Catalog filters, 3D globe, phone-orientation AR, pass alerts
