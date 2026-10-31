"""Web Push delivery (VAPID). Everything that needs `pywebpush` lives here, imported lazily,
so the rest of the app works without it."""
import base64
import json
import logging
import os

from backend import config

log = logging.getLogger(__name__)

_vapid = None  # cached py_vapid.Vapid


def available() -> bool:
    try:
        import pywebpush  # noqa: F401

        return True
    except ImportError:
        return False


def _load_vapid():
    """The server's VAPID key: from VAPID_PRIVATE_KEY, else the key file (created if missing)."""
    global _vapid
    if _vapid is not None:
        return _vapid
    from py_vapid import Vapid

    if config.VAPID_PRIVATE_KEY.strip():
        pem = config.VAPID_PRIVATE_KEY.replace("\\n", "\n").encode()
        _vapid = Vapid.from_pem(pem)
        return _vapid
    path = config.VAPID_KEY_PATH
    if path.exists():
        _vapid = Vapid.from_file(str(path))
    else:
        v = Vapid()
        v.generate_keys()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(v.private_pem())
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        log.info("Created a new VAPID key at %s", path)
        _vapid = v
    return _vapid


def public_key() -> str:
    """The application server key browsers need to subscribe (URL-safe base64, uncompressed point)."""
    from cryptography.hazmat.primitives import serialization

    raw = _load_vapid().public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def send(sub: dict, payload: dict, ttl: int = 1800) -> str:
    """Deliver one notification. Returns "ok", "gone" (the browser unsubscribed: delete it)
    or "error" (try again later)."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
            data=json.dumps(payload),
            vapid_private_key=_load_vapid(),
            vapid_claims={"sub": config.VAPID_SUBJECT},
            ttl=ttl,
            timeout=10,
        )
        return "ok"
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            return "gone"
        log.warning("Push failed (%s): %s", status, exc)
        return "error"
    except Exception as exc:
        log.warning("Push failed: %s", exc)
        return "error"
