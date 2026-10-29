"""A small per-client rate limit, so one script or a runaway browser tab can't use all the CPU.

Each client IP gets a token bucket: it can burst up to RATE_LIMIT_PER_MINUTE requests and the
bucket refills at that rate per minute. A normal browser tab makes about 40 requests a minute
(see the polling intervals in the frontend), so the default leaves room for several tabs or a
shared office address. Over the limit the answer is 429 with a Retry-After header.

State lives in memory, per process: fine for one server, not a shared limit across several.
Set RATE_LIMIT_PER_MINUTE=0 to switch it off. Behind a reverse proxy every request seems to come
from the proxy; set RATE_LIMIT_TRUST_FORWARDED=1 to use the first X-Forwarded-For address instead
(only when a proxy you control sets that header, because clients can fake it).
"""
import json
import threading
import time

from backend import config

EXEMPT_PATHS = {"/", "/health"}
_MAX_CLIENTS = 10_000


class TokenBuckets:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets = {}  # key -> [tokens, last_seen]

    def reset(self):
        with self._lock:
            self._buckets.clear()

    def take(self, key: str, per_minute: float):
        """(allowed, seconds to wait if not allowed)."""
        rate = per_minute / 60.0
        now = self._clock()
        with self._lock:
            tokens, last = self._buckets.get(key, (per_minute, now))
            tokens = min(per_minute, tokens + (now - last) * rate)
            if tokens >= 1:
                self._buckets[key] = [tokens - 1, now]
                allowed, wait = True, 0.0
            else:
                self._buckets[key] = [tokens, now]
                allowed, wait = False, (1 - tokens) / rate
            if len(self._buckets) > _MAX_CLIENTS:
                self._prune(now, per_minute)
            return allowed, wait

    def _prune(self, now, per_minute):
        # forget clients whose bucket would be full again by now
        rate = per_minute / 60.0
        for key in [k for k, (t, last) in self._buckets.items() if t + (now - last) * rate >= per_minute]:
            del self._buckets[key]


buckets = TokenBuckets()


def _client_key(scope) -> str:
    if config.RATE_LIMIT_TRUST_FORWARDED:
        for name, value in scope.get("headers", []):
            if name == b"x-forwarded-for":
                first = value.decode("latin-1").split(",")[0].strip()
                if first:
                    return first
    client = scope.get("client")
    return client[0] if client else "unknown"


class RateLimitMiddleware:
    """Plain ASGI middleware (cheaper than Starlette's BaseHTTPMiddleware)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        per_minute = config.RATE_LIMIT_PER_MINUTE
        if (
            scope["type"] != "http"
            or per_minute <= 0
            or scope["method"] == "OPTIONS"  # CORS preflight
            or scope["path"] in EXEMPT_PATHS
        ):
            return await self.app(scope, receive, send)

        allowed, wait = buckets.take(_client_key(scope), per_minute)
        if allowed:
            return await self.app(scope, receive, send)

        retry = max(1, int(wait + 0.999))
        body = json.dumps({"detail": f"Too many requests. Try again in {retry} s."}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(retry).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
