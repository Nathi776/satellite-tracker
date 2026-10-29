"""How long does a request wait while new orbit data arrives?

    python -m backend.tools.refresh_stall [-n 16000]

Serves /observer/visibility in a loop while a refresh happens (a new TLE download), and reports
the slowest request, once with the old behaviour (the first request after the refresh rebuilds
the catalogue) and once with the background refresher.
"""
import argparse
import logging
import threading
import time
from datetime import datetime, timezone

from backend import config
from backend.services import refresher
from backend.services import satellites as catalog
from backend.services import tle_service
from backend.tools.benchmark import synthetic_tles

PARAMS = {"lat": -25.75, "lon": 28.19, "hours": 24}


def _reset(tles):
    refresher.stop()
    tle_service.reset_for_tests()
    catalog._cache.update(version=None, snapshot=({}, [], {}))
    tle_service._install(tles, datetime.now(timezone.utc), "benchmark")
    tle_service._save_to_disk = lambda *a, **k: None


def _worst_request_ms(client, do_refresh, seconds=14):
    latencies, stop = [], threading.Event()

    def hammer():
        while not stop.is_set():
            t0 = time.perf_counter()
            client.get("/observer/visibility", params=PARAMS)
            latencies.append((time.perf_counter() - t0) * 1000)

    th = threading.Thread(target=hammer)
    th.start()
    time.sleep(2)
    do_refresh()
    time.sleep(seconds - 2)
    stop.set()
    th.join()
    latencies.sort()
    return latencies[-1], latencies[len(latencies) // 2], len(latencies)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=16000)
    args = ap.parse_args(argv)
    from fastapi.testclient import TestClient
    from backend.main import app

    logging.disable(logging.INFO)
    tles = synthetic_tles(args.n)
    tles2 = synthetic_tles(args.n, seed=2)
    config.TLE_CACHE_PATH = config.TLE_CACHE_PATH.parent / "benchmark_tle_cache.json"
    config.REFRESH_IN_BACKGROUND = False

    # old behaviour: the refresh just bumps the data version; a request pays for the rebuild
    _reset(tles)
    catalog.get_satellites()
    with TestClient(app) as client:
        client.get("/observer/visibility", params=PARAMS)
        w, m, n = _worst_request_ms(client, lambda: tle_service._install(tles2, datetime.now(timezone.utc), "x"))
    print(f"before: slowest request {w:7.0f} ms  (typical {m:.0f} ms, {n} requests)")

    # new behaviour: the refresher builds the new catalogue while requests use the old one
    _reset(tles)
    catalog.get_satellites()
    tle_service.set_background(True)
    with TestClient(app) as client:
        client.get("/observer/visibility", params=PARAMS)

        def refresh():
            tle_service._install(tles2, datetime.now(timezone.utc), "x")
            threading.Thread(target=catalog.warm).start()

        w, m, n = _worst_request_ms(client, refresh)
    print(f"after:  slowest request {w:7.0f} ms  (typical {m:.0f} ms, {n} requests)")
    refresher.stop()


if __name__ == "__main__":
    main()
