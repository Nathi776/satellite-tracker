"""Background pass alerts: a push notification shortly before a satellite becomes visible.

A thread wakes up every PUSH_CHECK_SECONDS. For each place that has subscribers it looks at the
upcoming passes of the watchlist satellites (recomputed every 10 minutes, shared by everyone
within ~1 km) and sends each subscriber a notification once, `lead_minutes` before the pass
starts. "Starts" means when the satellite becomes visible to the naked eye if it does, else when
it rises. By default only passes you could actually see are announced.
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from backend import config
from backend.services import pushsender, pushstore
from backend.services import satellites as catalog
from backend.services import visibility

log = logging.getLogger(__name__)

PASS_CACHE_SECONDS = 600
LOOKAHEAD_HOURS = 4  # longer than the longest allowed lead time
MAX_LEAD_MINUTES = 120

_cache: dict = {}
_stop = threading.Event()
_thread = None


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)


def pass_start(p: dict) -> datetime:
    """When to count the pass as starting: visible-from if you will see it, else the rise."""
    return _parse(p["visible_from_utc"] if p.get("visible_from_utc") else p["rise_time_utc"])


def due_passes(passes, now: datetime, lead_minutes: int, visible_only: bool) -> list:
    """Passes whose notification time has come and whose start has not: (pass, start, key)."""
    lead = timedelta(minutes=lead_minutes)
    out = []
    for p in passes:
        if visible_only and p.get("visibility") != "visible":
            continue
        start = pass_start(p)
        if start - lead <= now < start:
            out.append((p, start, f"{p['name']}|{p['rise_time_utc']}"))
    return out


def message(p: dict, start: datetime, now: datetime) -> dict:
    minutes = max(1, round((start - now).total_seconds() / 60))
    seen = p.get("visibility") == "visible"
    where = f"{p['rise_direction']} → {p['set_direction']}"
    detail = f"peaks {round(p['max_elevation_deg'])}° up, {where}"
    if seen and p.get("magnitude") is not None:
        detail += f", mag {p['magnitude']:+.1f}"
    return {
        "title": f"{p['name']} {'visible' if seen else 'rises'} in {minutes} min",
        "body": detail[0].upper() + detail[1:] + (". Look up!" if seen else "."),
        "tag": f"{p['name']}|{p['rise_time_utc']}",
        "url": f"/#/satellite/{p['name']}",
    }


def _passes_for(lat: float, lon: float, now_s: float) -> list:
    key = (round(lat, 2), round(lon, 2), catalog.get_version())
    hit = _cache.get(key)
    if hit and now_s - hit[0] < PASS_CACHE_SECONDS:
        return hit[1]
    observer = visibility._observer(key[0], key[1], 0.0)
    watchlist = catalog.match_prefixes(config.PASS_WATCHLIST)
    passes = visibility.compute_passes(watchlist, observer, visibility.ts.now(), hours=LOOKAHEAD_HOURS)
    _cache.clear() if len(_cache) > 500 else None
    _cache[key] = (now_s, passes)
    return passes


def run_once(now: datetime | None = None, send=None) -> int:
    """One pass over all subscriptions. Returns how many notifications were sent."""
    now = now or datetime.now(timezone.utc)
    send = send or pushsender.send
    sent = 0
    for sub in pushstore.all_subscriptions():
        try:
            passes = _passes_for(sub["lat"], sub["lon"], now.timestamp())
            for p, start, key in due_passes(passes, now, sub["lead_minutes"], bool(sub["visible_only"])):
                if not pushstore.mark_sent(sub["id"], key):
                    continue
                result = send(sub, message(p, start, now))
                if result == "ok":
                    sent += 1
                elif result == "gone":
                    pushstore.delete(sub["endpoint"])
                    break
                else:  # temporary failure: let the next round try again
                    pushstore.unmark_sent(sub["id"], key)
        except Exception as exc:
            log.warning("Alert check failed for one subscription: %s", exc)
    pushstore.prune_sent()
    return sent


def _loop():
    while not _stop.wait(config.PUSH_CHECK_SECONDS):
        try:
            run_once()
        except Exception as exc:
            log.warning("Alert round failed: %s", exc)


def enabled() -> bool:
    return bool(config.PUSH_ENABLED and pushsender.available())


def start() -> None:
    global _thread
    if not enabled() or (_thread is not None and _thread.is_alive()):
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="pass-alerts", daemon=True)
    _thread.start()
    log.info("Pass alerts running (every %ds)", config.PUSH_CHECK_SECONDS)


def stop() -> None:
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)
    _thread = None
