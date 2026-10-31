"""Pass alerts: which passes are due, who gets told once, and the subscription endpoints."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.main import app
from backend.services import alerts, pushsender, pushstore

pytest.importorskip("pywebpush")

NOW = datetime(2026, 10, 30, 18, 0, 0, tzinfo=timezone.utc)
iso = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_pass(rise_in_min, visibility="visible", visible_in_min=None, name="ISS (ZARYA)"):
    rise = NOW + timedelta(minutes=rise_in_min)
    p = {
        "name": name, "rise_time_utc": iso(rise), "rise_direction": "WSW", "set_direction": "NE",
        "max_elevation_deg": 62.4, "visibility": visibility, "magnitude": -3.1,
        "visible_from_utc": None, "visible_until_utc": None,
    }
    if visibility == "visible":
        p["visible_from_utc"] = iso(NOW + timedelta(minutes=visible_in_min if visible_in_min is not None else rise_in_min))
    return p


SUB = {"endpoint": "https://push.example/abc123456", "keys": {"p256dh": "P" * 30, "auth": "A" * 12}}


# ---- which passes are due ------------------------------------------------------------
def test_due_only_inside_the_lead_window():
    passes = [make_pass(5), make_pass(30), make_pass(-3, visible_in_min=-2)]
    due = alerts.due_passes(passes, NOW, lead_minutes=10, visible_only=True)
    assert [p["rise_time_utc"] for p, _, _ in due] == [passes[0]["rise_time_utc"]]  # 30 min: too early; started: too late


def test_visible_only_skips_passes_you_could_not_see():
    passes = [make_pass(5, visibility="daylight"), make_pass(6, visibility="faint")]
    assert alerts.due_passes(passes, NOW, 10, visible_only=True) == []
    assert len(alerts.due_passes(passes, NOW, 10, visible_only=False)) == 2


def test_start_is_when_it_becomes_visible_not_when_it_rises():
    p = make_pass(5, visible_in_min=20)  # rises in 5 min but only visible from +20
    assert alerts.due_passes([p], NOW, 10, True) == []
    assert len(alerts.due_passes([p], NOW + timedelta(minutes=11), 10, True)) == 1


def test_message_text():
    p = make_pass(5)
    m = alerts.message(p, alerts.pass_start(p), NOW)
    assert m["title"] == "ISS (ZARYA) visible in 5 min"
    assert "62° up" in m["body"] and "WSW → NE" in m["body"] and "mag -3.1" in m["body"]
    assert m["url"] == "/#/satellite/ISS (ZARYA)"
    m2 = alerts.message(make_pass(5, "daylight"), NOW + timedelta(minutes=5), NOW)
    assert m2["title"].endswith("rises in 5 min") or "rises" in m2["title"]


# ---- run_once -----------------------------------------------------------------------
@pytest.fixture
def subscribed(monkeypatch):
    pushstore.upsert(SUB["endpoint"], "P" * 30, "A" * 12, -25.75, 28.19, 10, True)
    monkeypatch.setattr(alerts, "_passes_for", lambda lat, lon, now_s: [make_pass(5), make_pass(90)])


def test_each_pass_is_sent_once(subscribed):
    sent = []
    send = lambda sub, payload: sent.append(payload) or "ok"
    assert alerts.run_once(NOW, send) == 1
    assert alerts.run_once(NOW + timedelta(minutes=1), send) == 0  # same pass, not repeated
    assert len(sent) == 1 and "ISS (ZARYA)" in sent[0]["title"]


def test_a_temporary_failure_is_retried_next_round(subscribed):
    results = iter(["error", "ok"])
    calls = []
    send = lambda sub, payload: calls.append(1) or next(results)
    assert alerts.run_once(NOW, send) == 0
    assert alerts.run_once(NOW + timedelta(minutes=1), send) == 1
    assert len(calls) == 2


def test_a_gone_subscription_is_deleted(subscribed):
    assert alerts.run_once(NOW, lambda s, p: "gone") == 0
    assert pushstore.get(SUB["endpoint"]) is None


def test_subscriber_settings_are_respected(monkeypatch):
    pushstore.upsert("https://push.example/other00001", "P" * 30, "A" * 12, 0.0, 0.0, 3, True)
    monkeypatch.setattr(alerts, "_passes_for", lambda lat, lon, now_s: [make_pass(5)])
    sent = []
    alerts.run_once(NOW, lambda s, p: sent.append(1) or "ok")
    assert sent == []  # lead is 3 min, the pass is 5 min away


# ---- store ---------------------------------------------------------------------------
def test_store_upsert_update_delete_and_limit(monkeypatch):
    assert pushstore.upsert("https://x.example/1111111111", "p" * 20, "a" * 10, 1, 2, 10, True)
    assert pushstore.upsert("https://x.example/1111111111", "q" * 20, "b" * 10, 3, 4, 20, False)  # update
    rows = pushstore.all_subscriptions()
    assert len(rows) == 1 and rows[0]["lead_minutes"] == 20 and rows[0]["visible_only"] == 0 and rows[0]["lat"] == 3
    monkeypatch.setattr(config, "PUSH_MAX_SUBSCRIPTIONS", 1)
    assert not pushstore.upsert("https://x.example/2222222222", "p" * 20, "a" * 10, 1, 2, 10, True)
    assert pushstore.upsert("https://x.example/1111111111", "q" * 20, "b" * 10, 3, 4, 20, False)  # existing still fine
    assert pushstore.delete("https://x.example/1111111111") and not pushstore.delete("https://x.example/1111111111")


# ---- HTTP ----------------------------------------------------------------------------
@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_key_endpoint_serves_a_valid_public_key(client):
    body = client.get("/push/key").json()
    assert body["enabled"] is True
    key = body["public_key"]
    import base64

    raw = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
    assert len(raw) == 65 and raw[0] == 4  # an uncompressed P-256 point
    assert client.get("/push/key").json()["public_key"] == key  # stable
    assert config.VAPID_KEY_PATH.exists()


def test_vapid_key_survives_a_restart(client, monkeypatch):
    first = client.get("/push/key").json()["public_key"]
    monkeypatch.setattr(pushsender, "_vapid", None)  # a new process reads the file
    assert client.get("/push/key").json()["public_key"] == first


def test_subscribe_validates_and_rounds_the_location(client):
    good = {"subscription": SUB, "lat": -25.7479, "lon": 28.2293, "lead_minutes": 15, "visible_only": False}
    assert client.post("/push/subscribe", json=good).json()["subscribed"] is True
    row = pushstore.get(SUB["endpoint"])
    assert (row["lat"], row["lon"], row["lead_minutes"], row["visible_only"]) == (-25.75, 28.23, 15, 0)

    bad = [
        {**good, "lat": 91}, {**good, "lon": 181}, {**good, "lead_minutes": 0}, {**good, "lead_minutes": 500},
        {**good, "subscription": {**SUB, "endpoint": "http://insecure.example/abcdef"}},
        {**good, "subscription": {"endpoint": SUB["endpoint"]}},
    ]
    for b in bad:
        assert client.post("/push/subscribe", json=b).status_code == 422, b


def test_unsubscribe(client):
    client.post("/push/subscribe", json={"subscription": SUB, "lat": 0, "lon": 0})
    assert client.post("/push/unsubscribe", json={"endpoint": SUB["endpoint"]}).json() == {"removed": True}
    assert client.post("/push/unsubscribe", json={"endpoint": SUB["endpoint"]}).json() == {"removed": False}


def test_test_endpoint(client, monkeypatch):
    assert client.post("/push/test", json={"endpoint": SUB["endpoint"]}).status_code == 404
    client.post("/push/subscribe", json={"subscription": SUB, "lat": 0, "lon": 0})
    monkeypatch.setattr(pushsender, "send", lambda sub, payload: "ok")
    assert client.post("/push/test", json={"endpoint": SUB["endpoint"]}).json() == {"sent": True}
    monkeypatch.setattr(pushsender, "send", lambda sub, payload: "gone")
    assert client.post("/push/test", json={"endpoint": SUB["endpoint"]}).status_code == 410
    assert pushstore.get(SUB["endpoint"]) is None


def test_disabled_server_reports_it(client, monkeypatch):
    monkeypatch.setattr(config, "PUSH_ENABLED", False)
    assert client.get("/push/key").json() == {"enabled": False, "public_key": None}
    assert client.post("/push/subscribe", json={"subscription": SUB, "lat": 0, "lon": 0}).status_code == 503


def test_real_passes_for_a_location_have_what_alerts_need():
    """The pass dicts from the real calculation carry every field the alert code reads."""
    passes = alerts._passes_for(-25.75, 28.19, 0.0)
    for p in passes[:5]:
        alerts.pass_start(p)
        alerts.message(p, alerts.pass_start(p), NOW)


# ---- the real encryption path, against a fake push service ------------------------------
def test_send_produces_a_message_the_browser_could_decrypt(monkeypatch):
    """Build a subscription like a browser would, send for real with `requests.post` captured,
    then decrypt the body with the browser's private key and check the VAPID header."""
    import base64
    import json

    import http_ece
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    unb64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

    browser_key = ec.generate_private_key(ec.SECP256R1())
    p256dh = b64(browser_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    auth = b64(b"0123456789abcdef")
    sub = {"endpoint": "https://push.example/send/xyz", "p256dh": p256dh, "auth": auth}

    captured = {}

    class Resp:
        status_code = 201
        text = ""
        headers = {}
        ok = True

        def raise_for_status(self):
            pass

    def fake_post(url, data=None, headers=None, **kw):
        captured.update(url=url, data=data, headers=headers)
        return Resp()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    payload = {"title": "ISS (ZARYA) visible in 5 min", "body": "Look up!", "tag": "t", "url": "/"}
    assert pushsender.send(sub, payload) == "ok"
    assert captured["url"] == sub["endpoint"]

    plain = http_ece.decrypt(
        captured["data"], private_key=browser_key, auth_secret=unb64(auth), version="aes128gcm"
    )
    assert json.loads(plain) == payload
    # the VAPID header names our public key, so push services can tie the message to this server
    assert pushsender.public_key() in captured["headers"]["authorization"] or pushsender.public_key() in captured["headers"].get("crypto-key", "")
