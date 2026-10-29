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
| `GET /health` | Status, how fresh the TLE data is, and the state of the background refresh |
| `GET /groups` | Catalog groups (Stations, Africa, Weather, Navigation, Starlink, OneWeb, Comms, Other) with counts |
| `GET /positions?search=&group=&limit=&at=&names=` | Position, altitude, speed, period and footprint radius of matching satellites. `group` filters before `limit` (max 2000) and takes one id or several separated by commas (`stations,weather`); with several, the limit is shared fairly so a big group cannot fill every slot; `at` (ISO time, naive = UTC) shows any moment within ±48 h, else `422`. `names` (repeat it) fetches exactly those satellites and ignores the other filters; the Favourites filter uses it |
| `GET /africa` | African satellites by country with their current position, plus `unmatched`: name-table entries that match nothing in today's catalog |
| `GET /africa/passes?lat=&lon=&hours=` | Passes of every African satellite over a spot, visible or not (cubesat radio and imaging passes matter even by day) |
| `GET /satellite/{name}` | One satellite's current position |
| `GET /satellite/{name}/view?lat=&lon=&hours=` | Where to look for one satellite from a spot: azimuth, elevation (negative = below the horizon), distance, sunlit, magnitude, visibility status, per-second motion rates, plus its next pass and the next five (`passes`) |
| `GET /satellite/{name}/info` | Orbit facts for one satellite: NORAD id, inclination, period, perigee/apogee, eccentricity, age of the element set, and a short description |
| `GET /iss` | The ISS's current position |
| `GET /groundtrack/{name}?minutes=&step=&at=` | Ground track starting now, or at `at` |
| `GET /observer/visibility?lat=&lon=&hours=&naked_eye_only=` | Your sky: how dark it is, every satellite above your horizon (elevation, azimuth, range, sunlit?, estimated magnitude, per-second motion rates) and upcoming passes (up to 72 h) classified as `visible`, `faint`, `in_shadow` or `daylight` |
| `GET /passes/calendar.ics?lat=&lon=&hours=&naked_eye_only=` | Upcoming passes as an iCalendar file, each with a 10-minute alarm. Import it into Google/Apple/Outlook calendar for reminders on any device |
| `GET /passes/iss?lat=&lon=` | ISS passes over a location |
| `GET /passes/african/{name}?lat=&lon=` | Passes of a named satellite (defaults to Pretoria) |

Name matching ignores case, spaces and punctuation (`zacube 1` finds `ZACUBE-1`).
Unknown satellites return `404`; invalid coordinates return `422`.

## Groups, time travel and footprints

Groups come from satellite **names** (e.g. `STARLINK-…`, `NOAA …`, `GPS …`), so they are a
good heuristic, not an official classification. "Africa" matches the name tokens in
the table in `backend/services/africa.py` (name prefix -> country; add your own via `EXTRA_ENTRIES` in `backend/config.py`). It was written without access to the live feed, so open `GET /africa` and check `unmatched` to see which entries match nothing today. Time travel is limited to `MAX_TIME_TRAVEL_HOURS`
(default 48); orbits get less accurate the further from the TLE epoch. The footprint circle is the
area from which the satellite is above the horizon.

## Map and look

- **Map styles:** Dark (default, Esri Dark Gray; CARTO's free dark tiles now require an API key), Satellite (Esri imagery) and Street (OpenStreetMap). Your choice is remembered in the browser. The tiles come from third-party servers, so check they load on your network.
- **Night shading:** the day/night terminator with civil, nautical and astronomical twilight bands, computed from the Sun's position for the time shown (so it follows time travel).
- **You are here:** a pulsing marker with a dashed circle of roughly 1,570 km, the furthest a low-orbit satellite can be and still be above your horizon.
- **Orbit:** the selected satellite shows its past track (dashed) and future track (solid).
- **Desktop layout (≥ 1000 px wide):** the map fills the window. A **Layers** panel on the left holds the satellite groups (tick several at once, with counts) and the overlays: ground track, day/night, your range, footprint, labels, and satellites above you. The selected satellite (or "Your sky") is one column on the right. A **status bar** under the map shows UTC time, the pointer's coordinates, tracked / on-map / above-you counts, the selected satellite's altitude, speed and position, and how old the sky data is. Between 721 and 999 px the Layers panel becomes the same sheet as on phones. The orbit track can also be switched off per satellite.
- **Keyboard shortcuts** (wide screens, not while typing): `S` cycles the map style, `D` day/night, `T` ground track, `O` your range, `F` footprint, `L` labels, `/` focuses search, `Esc` clears the selection. Overlay choices are remembered in the browser.
- **Satellite pages and favourites:** tap ☆ on a satellite to keep it as a favourite (remembered in this browser; a ★ Favourites filter appears in the header). "View details" opens `#/satellite/<name>`: a map with its orbit, where to look from you, live position and speed, orbit facts and its next five passes with reminders. The page can be bookmarked or shared as a link. Your location is remembered for the browser tab so the map and the page agree.
- **Phones:** one bottom sheet holds the selected satellite and "Your sky". It rests low (a one-line summary), half-open or nearly full: drag the handle, or tap it to open and close. Picking a satellite opens it on that satellite, with a Satellite | Your sky switch. The rest: a compact header (search and a location button on one row, plus a **Layers** button that opens a sheet with the map style, satellite groups, overlays and the "show up to" limit), the time-travel slider folded into a small pill you tap to open, and the map credit in the top-left corner. Zoom is by pinch.
- **Selected satellite:** tap one and (with your location set) the card shows where to look (azimuth, elevation, distance), whether you can see it, and its next pass. It is live-only, so it is replaced by a note while you time-travel. Orbit facts sit under "Orbit details".
- **UTC clock:** live, offline or time-travel status with the date and time in UTC.

## Performance

`python -m backend.tools.benchmark` times the API against a synthetic catalogue of about 16,000
satellites (the size of CelesTrak's "active" group; add `--profile` to see where the time goes,
`-n 5000` for a smaller one). Measured on a 2-core sandbox:

| What | Before | After |
|---|---|---|
| Your sky, nobody has asked recently (`/observer/visibility`) | 2.4 s | 0.5 s |
| Same, within the 5-second cache | 30 ms | 30 ms |
| Every satellite above the horizon (the heavy part) | 2.3 s | 0.4 s |
| `/positions?limit=300` | 0.2 s | 0.2 s |
| `/positions?limit=2000` | 1.1 s | 1.1 s |
| Building the catalogue (once per TLE download, every 6 h) | 3.1 s | 3.1 s |

How: `services/prefilter.py` runs SGP4 for the whole catalogue at once and finds the roughly 5%
that can be above the horizon; the exact Skyfield calculation then runs only on those. The Sun's
position is looked up once per request instead of once per satellite. Results are identical to the
exact path (tests compare them for five observers, including near the pole, and check that no
satellite above the horizon is ever dropped).

Each browser asks for its sky every 5 seconds, and one request holds a CPU core for about half a
second, so budget roughly ten simultaneous people in *different* places per core (people within
about 1 km share one cached answer). The remaining big cost is `/positions` with a high limit.

**Refreshing the orbit data no longer stalls requests.** A background thread downloads new TLEs
when they pass their TTL, builds the new catalogue (and the vectorised SGP4 array) next to the old
one, and swaps it in as one step; requests keep using the old data until then. Failures keep the
old data and are retried after 1, 2, 4 ... up to 30 minutes; `/health` shows the last error, whether
a refresh is running and when the next one is due. On startup the saved disk copy is used straight
away while a fresh download happens in the background. `python -m backend.tools.refresh_stall`
measures it (16,000 synthetic satellites, requests running throughout a refresh):

| | Slowest request during a refresh |
|---|---|
| Before (first request after the download rebuilds the catalogue) | 4.5 s |
| After (background refresh) | 0.8 s |

The remaining 0.8 s is CPU sharing with the build (the cached sky answer is recomputed every 5 s
while the build runs), not waiting on a lock.

## How the data works

TLEs are downloaded from CelesTrak, cached in memory, and saved to
`backend/data/tle_cache.json`. They refresh every 6 hours. If CelesTrak is
unreachable, the API keeps serving the last data it has, including after a restart.

## What "visible" means

A satellite is reported as visible to the naked eye only when **all** of these hold:

1. **Dark sky:** the Sun is more than 6° below your horizon (end of civil twilight).
2. **Sunlit:** the satellite is not inside Earth's shadow (checked with Skyfield and the `de421.bsp` ephemeris).
3. **Bright enough:** its estimated apparent magnitude is at or below `NAKED_EYE_LIMIT_MAG`, and it is more than 10° above the horizon.

TLEs say nothing about a satellite's size or brightness, so (3) is only estimated for objects we
have a brightness figure for:

1. Hand-entered figures in `BRIGHT_STD_MAGS` (`backend/config.py`: ISS, Tiangong, Hubble). These win.
2. Mike McCants' `quicksat.mag` (bundled in `backend/resources/`), matched by NORAD number: about
   2,200 objects. Its "intrinsic magnitude" is the brightest the object gets, fully lit at 1000 km;
   we add 1.24 to convert it to the half-lit standard magnitude our formula uses.

Everything else is shown as *Too faint* when sunlit on a dark sky, never as visible. Treat file-based
magnitudes as optimistic: the catalogue is old (it stops at NORAD 36511, so Starlink and other recent
satellites are absent), tumbling and decayed objects are skipped, and rocket bodies can be a magnitude
or more fainter than their listed maximum. Data credit: Mike McCants, mmccants.org. Replace the file
with a newer copy any time.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `TLE_TTL_SECONDS` | `21600` | How long TLEs are reused before refreshing |
| `REFRESH_IN_BACKGROUND` | `1` | Refresh the orbit data in a background thread (`0`: the first request after the TTL does it) |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins. Set this when you deploy |
| `VISIBILITY_CACHE_SECONDS` | `5` | How long a visibility result is reused |
| `CELESTRAK_URL` | active satellites | TLE source |
| `DARK_SKY_SUN_ALTITUDE_DEG` | `-6` | Sun must be below this for the sky to count as dark |
| `MAX_TIME_TRAVEL_HOURS` | `48` | How far from now `at=` may reach |
| `QUICKSAT_MAG_PATH` | `backend/resources/quicksat.mag` | McCants' brightness catalogue. Point it at a newer copy, or at a missing file to switch it off |
| `NAKED_EYE_LIMIT_MAG` | `4.5` | Faintest magnitude treated as visible (~5.5 dark site, ~4 in a suburb) |

## Pass alerts

The sky panel has an **Add passes to my calendar** link (the `.ics` above) and a per-pass **Remind me**
button. The button uses browser notifications, so it only fires while the page stays open; use the
calendar file for reminders that work when the app is closed. True background push alerts would need
a server-side subscription store and are not built yet.

## Sky view on your phone

Open the sky panel, stay on the **Now** tab and tap **Open sky view**, then **Start**. Hold the phone
up: satellites appear where they are in the real sky, optionally over the rear camera. Tap one to follow
it; an arrow tells you which way to turn when it is off screen. On a computer (no sensors) you drag to look
around instead.

Phones only give web pages the compass and camera on **secure (https)** pages, and `127.0.0.1` on a phone is
the phone itself, so to try it on your own phone:

1. Start the backend as usual (`uvicorn backend.main:app --reload`).
2. In `frontend/`: `npm install` (once, it adds a dev-only HTTPS plugin), then `npm run dev:phone`.
3. On your phone (same Wi-Fi) open the `https://…:5173` "Network" address Vite prints and accept the
   self-signed certificate warning. Allow Node through the Windows firewall if asked.

Notes: phone compasses point to *magnetic* north, so the app adds the magnetic declination at your location
(from the World Magnetic Model via `pygeomag`, about −20° in Pretoria; `GET /observer/declination`). Portrait only; the field of view is a typical phone camera (65°, `FOV_V` in `SkyView.tsx`). On
Android Chrome the compass is absolute. On iPhone the heading comes from `webkitCompassHeading`, which this app
has not been tested with on a real device. If north looks wrong, use the **Compass fix** slider until the
heading at the top matches a compass app. Compass accuracy near metal, or a phone that has not been calibrated
(wave it in a figure of eight), is often 10° or worse, so expect satellites to be near, not exactly on, the
camera image.

## Roadmap

- Marker clustering was skipped on purpose (it fights moving satellites; a canvas layer is used instead)
- 3D globe, phone-orientation AR, pass alerts
- Brightness data for more satellites (beyond ISS, Tiangong and Hubble)
