"""Push subscriptions and what has already been sent, in a small SQLite file."""
import hashlib
import sqlite3
import threading
import time
from contextlib import contextmanager

from backend import config

_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,           -- sha256 of the endpoint
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    lead_minutes INTEGER NOT NULL,
    visible_only INTEGER NOT NULL,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sent (
    sub_id TEXT NOT NULL,
    key TEXT NOT NULL,
    sent_at REAL NOT NULL,
    PRIMARY KEY (sub_id, key)
);
"""


@contextmanager
def _db():
    path = config.PUSH_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(_SCHEMA)
            yield conn
            conn.commit()
        finally:
            conn.close()


def sub_id(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()[:32]


def count() -> int:
    with _db() as db:
        return db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]


def upsert(endpoint, p256dh, auth, lat, lon, lead_minutes, visible_only) -> bool:
    """Add or update a subscription. False if the store is full (and this one is new)."""
    now = time.time()
    sid = sub_id(endpoint)
    with _db() as db:
        exists = db.execute("SELECT 1 FROM subscriptions WHERE id=?", (sid,)).fetchone()
        if not exists and db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0] >= config.PUSH_MAX_SUBSCRIPTIONS:
            return False
        db.execute(
            """INSERT INTO subscriptions (id, endpoint, p256dh, auth, lat, lon, lead_minutes, visible_only, created, updated)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET p256dh=excluded.p256dh, auth=excluded.auth, lat=excluded.lat,
                 lon=excluded.lon, lead_minutes=excluded.lead_minutes, visible_only=excluded.visible_only,
                 updated=excluded.updated""",
            (sid, endpoint, p256dh, auth, lat, lon, int(lead_minutes), int(bool(visible_only)), now, now),
        )
    return True


def delete(endpoint: str) -> bool:
    sid = sub_id(endpoint)
    with _db() as db:
        db.execute("DELETE FROM sent WHERE sub_id=?", (sid,))
        return db.execute("DELETE FROM subscriptions WHERE id=?", (sid,)).rowcount > 0


def get(endpoint: str):
    with _db() as db:
        row = db.execute("SELECT * FROM subscriptions WHERE id=?", (sub_id(endpoint),)).fetchone()
        return dict(row) if row else None


def all_subscriptions() -> list:
    with _db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM subscriptions")]


def mark_sent(sid: str, key: str) -> bool:
    """Record that `key` was sent to this subscription. False if it had been already."""
    with _db() as db:
        return db.execute("INSERT OR IGNORE INTO sent (sub_id, key, sent_at) VALUES (?,?,?)", (sid, key, time.time())).rowcount == 1


def unmark_sent(sid: str, key: str) -> None:
    with _db() as db:
        db.execute("DELETE FROM sent WHERE sub_id=? AND key=?", (sid, key))


def prune_sent(older_than_s: float = 3 * 86400) -> None:
    with _db() as db:
        db.execute("DELETE FROM sent WHERE sent_at < ?", (time.time() - older_than_s,))
