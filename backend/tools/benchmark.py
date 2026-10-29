"""Time the API against a large catalogue.

CelesTrak's "active" group is about 15,000 satellites. This builds a synthetic catalogue of
that size (mostly Starlink-like orbits, plus OneWeb, GPS-like and others) so the timings can
be reproduced without a download:

    python -m backend.tools.benchmark            # 16,000 satellites
    python -m backend.tools.benchmark -n 5000
    python -m backend.tools.benchmark --profile  # also show where the time goes

Nothing here touches your real TLE cache.
"""
import argparse
import logging
import cProfile
import io
import math
import pstats
import random
import sys
import time
import resource
from datetime import datetime, timezone

from sgp4.api import WGS72, Satrec
from sgp4.exporter import export_tle

from backend import config
from backend.services import satellites as catalog
from backend.services import tle_service, visibility

# (name prefix, share, altitude km, inclination deg)
SHELLS = [
    ("STARLINK", 0.70, 550, 53.0),
    ("STARLINK", 0.08, 560, 97.6),
    ("ONEWEB", 0.04, 1200, 87.9),
    ("COSMOS", 0.06, 800, 74.0),
    ("NOAA", 0.01, 850, 98.7),
    ("GPS BIIR", 0.01, 20200, 55.0),
    ("IRIDIUM", 0.01, 780, 86.4),
    ("OBJECT", 0.09, 500, 51.6),
]
MU = 398600.4418


def synthetic_tles(n: int, seed: int = 1) -> dict:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    # sgp4 epoch: days since 1949-12-31 00:00 UTC
    epoch = (now - datetime(1949, 12, 31, tzinfo=timezone.utc)).total_seconds() / 86400.0
    tles = {}
    k = 0
    for prefix, share, alt, inc in SHELLS:
        for _ in range(int(n * share)):
            k += 1
            a = 6378.137 + alt + rng.uniform(-15, 15)
            mean_motion = math.sqrt(MU / a**3) * 60.0  # rad/min
            sat = Satrec()
            sat.sgp4init(
                WGS72, "i", 40000 + k, epoch, 1e-4, 0.0, 0.0,
                rng.uniform(0.0001, 0.003), rng.uniform(0, 2 * math.pi),
                math.radians(inc + rng.uniform(-0.3, 0.3)), rng.uniform(0, 2 * math.pi),
                mean_motion, rng.uniform(0, 2 * math.pi),
            )
            line1, line2 = export_tle(sat)
            tles[f"{prefix}-{k}"] = {"line1": line1, "line2": line2}
    # make sure the satellites everyone looks for are there
    iss = Satrec()
    iss.sgp4init(WGS72, "i", 25544, epoch, 3e-5, 0.0, 0.0, 0.0003, 1.0,
                 math.radians(51.64), 2.0, math.sqrt(MU / (6378.137 + 417) ** 3) * 60.0, 3.0)
    tles["ISS (ZARYA)"] = dict(zip(("line1", "line2"), export_tle(iss)))
    return tles


class Timer:
    def __init__(self):
        self.rows = []

    def run(self, label, fn, repeat=1):
        best = None
        result = None
        for _ in range(repeat):
            t0 = time.perf_counter()
            result = fn()
            dt = time.perf_counter() - t0
            best = dt if best is None else min(best, dt)
        self.rows.append((label, best))
        print(f"{label:<58} {best * 1000:>9.1f} ms", flush=True)
        return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=16000, help="number of satellites")
    ap.add_argument("--profile", action="store_true", help="show the slowest functions")
    args = ap.parse_args(argv)

    from fastapi.testclient import TestClient
    from backend.main import app

    logging.disable(logging.INFO)  # keep the output to the timings
    t = Timer()
    print(f"Synthetic catalogue of about {args.n:,} satellites\n")
    tles = t.run("generate TLEs (not part of the app)", lambda: synthetic_tles(args.n))

    # install it as the "downloaded" data, without touching the disk cache or the network
    config.TLE_CACHE_PATH = config.TLE_CACHE_PATH.parent / "benchmark_tle_cache.json"
    tle_service.reset_for_tests()
    tle_service._install(tles, datetime.now(timezone.utc), "benchmark")
    tle_service._save_to_disk = lambda *a, **k: None

    text = "\n".join(f"{name}\n{v['line1']}\n{v['line2']}" for name, v in tles.items())
    t.run("parse TLE text (once per download)", lambda: tle_service.parse_tle_text(text))

    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t.run("build EarthSatellite objects (once per download)", lambda: catalog.get_satellites())
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"{'  memory added by the catalogue (peak, approx.)':<58} {(rss_after - rss_before) / 1024:>9.0f} MB\n")

    sats = list(catalog.get_satellites().values())
    observer = visibility._observer(-25.75, 28.19)
    now = visibility.ts.now()

    with TestClient(app) as client:
        for limit in (300, 2000):
            t.run(f"GET /positions?limit={limit}", lambda: client.get("/positions", params={"limit": limit}), repeat=3)
        t.run("GET /positions?group=starlink&limit=2000", lambda: client.get("/positions", params={"group": "starlink", "limit": 2000}), repeat=3)
        t.run("GET /groups", lambda: client.get("/groups"), repeat=3)

        t.run("visible_now over all satellites (the heavy part)", lambda: visibility.compute_visible_now(sats, observer, now))
        watch = catalog.match_prefixes(config.PASS_WATCHLIST)
        t.run(f"passes for the watchlist ({len(watch)} satellites, 24 h)", lambda: visibility.compute_passes(watch, observer, now))

        def cold():
            visibility._cache.clear()
            return client.get("/observer/visibility", params={"lat": -25.75, "lon": 28.19})

        r = t.run("GET /observer/visibility (cold, nobody cached)", cold)
        print(f"{'  satellites above the horizon':<58} {len(r.json()['visible_now']):>9}")
        t.run("GET /observer/visibility (warm, within the cache time)", lambda: client.get("/observer/visibility", params={"lat": -25.75, "lon": 28.19}), repeat=3)
        t.run("GET /satellite/ISS/view", lambda: client.get("/satellite/ISS/view", params={"lat": -25.75, "lon": 28.19}), repeat=3)

        if args.profile:
            print("\nProfile of one cold /observer/visibility:\n")
            visibility._cache.clear()
            pr = cProfile.Profile()
            pr.enable()
            client.get("/observer/visibility", params={"lat": -25.75, "lon": 28.19})
            pr.disable()
            out = io.StringIO()
            pstats.Stats(pr, stream=out).strip_dirs().sort_stats("tottime").print_stats(14)
            print(out.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
