import pytest
from fastapi.testclient import TestClient

from backend import config, ratelimit
from backend.main import app


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_bucket_allows_a_burst_then_refills():
    clock = FakeClock()
    b = ratelimit.TokenBuckets(clock)
    assert all(b.take("a", 60)[0] for _ in range(60))  # a full minute's worth at once
    allowed, wait = b.take("a", 60)
    assert not allowed and 0 < wait <= 1.0
    clock.t += 2  # two seconds: two tokens at 1/s
    assert b.take("a", 60)[0] and b.take("a", 60)[0]
    assert not b.take("a", 60)[0]


def test_clients_are_independent():
    b = ratelimit.TokenBuckets(FakeClock())
    for _ in range(5):
        b.take("a", 5)
    assert not b.take("a", 5)[0]
    assert b.take("b", 5)[0]


def test_idle_clients_are_forgotten(monkeypatch):
    clock = FakeClock()
    b = ratelimit.TokenBuckets(clock)
    monkeypatch.setattr(ratelimit, "_MAX_CLIENTS", 10)
    for i in range(10):
        b.take(f"c{i}", 60)
    clock.t += 120  # everyone's bucket is full again
    b.take("new", 60)
    assert len(b._buckets) == 1


@pytest.fixture
def limited(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 3)
    ratelimit.buckets.reset()
    with TestClient(app) as c:
        yield c
    ratelimit.buckets.reset()


def test_api_returns_429_with_retry_after(limited):
    codes = [limited.get("/groups").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
    r = limited.get("/groups")
    assert int(r.headers["retry-after"]) >= 1
    assert "Too many requests" in r.json()["detail"]


def test_429_still_carries_cors_headers(limited):
    for _ in range(3):
        limited.get("/groups")
    r = limited.get("/groups", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 429
    assert r.headers.get("access-control-allow-origin") in ("*", "http://localhost:5173")


def test_health_and_preflight_are_never_limited(limited):
    for _ in range(10):
        assert limited.get("/health").status_code == 200
    for _ in range(3):
        limited.get("/groups")
    pre = limited.options(
        "/groups",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert pre.status_code == 200


def test_forwarded_header_only_trusted_when_enabled(monkeypatch, limited):
    for _ in range(3):
        limited.get("/groups")
    # not trusted: a spoofed header doesn't give a fresh allowance
    assert limited.get("/groups", headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 429
    monkeypatch.setattr(config, "RATE_LIMIT_TRUST_FORWARDED", True)
    assert limited.get("/groups", headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 200


def test_zero_switches_it_off(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 0)
    with TestClient(app) as c:
        assert all(c.get("/groups").status_code == 200 for _ in range(20))
