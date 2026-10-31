"""HTTP endpoints for pass alerts (Web Push subscriptions)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import config
from backend.services import alerts, pushsender, pushstore

router = APIRouter(prefix="/push", tags=["push"])


class Keys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=6, max_length=100)


class Subscription(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: Keys


class SubscribeBody(BaseModel):
    subscription: Subscription
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    lead_minutes: int = Field(default=10, ge=1, le=alerts.MAX_LEAD_MINUTES)
    visible_only: bool = True


class UnsubscribeBody(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)


def _require_enabled():
    if not alerts.enabled():
        raise HTTPException(status_code=503, detail="Pass alerts are not available on this server")


@router.get("/key")
def get_key():
    """The public key a browser needs to subscribe, and whether alerts work on this server."""
    if not alerts.enabled():
        return {"enabled": False, "public_key": None}
    return {"enabled": True, "public_key": pushsender.public_key()}


@router.post("/subscribe")
def subscribe(body: SubscribeBody):
    """Save (or update) a browser's alert settings. The location is rounded to ~1 km."""
    _require_enabled()
    if not body.subscription.endpoint.startswith("https://"):
        raise HTTPException(status_code=422, detail="Push endpoints must be https")
    ok = pushstore.upsert(
        body.subscription.endpoint,
        body.subscription.keys.p256dh,
        body.subscription.keys.auth,
        round(body.lat, 2),
        round(body.lon, 2),
        body.lead_minutes,
        body.visible_only,
    )
    if not ok:
        raise HTTPException(status_code=503, detail="Too many subscriptions on this server")
    return {"subscribed": True, "lead_minutes": body.lead_minutes, "visible_only": body.visible_only}


@router.post("/unsubscribe")
def unsubscribe(body: UnsubscribeBody):
    return {"removed": pushstore.delete(body.endpoint)}


@router.post("/test")
def send_test(body: UnsubscribeBody):
    """Send a test notification to a subscribed browser, so people can check it works."""
    _require_enabled()
    sub = pushstore.get(body.endpoint)
    if not sub:
        raise HTTPException(status_code=404, detail="Not subscribed")
    result = pushsender.send(
        sub, {"title": "Pass alerts are on", "body": "You will be told shortly before satellites pass.", "tag": "test", "url": "/"}
    )
    if result == "gone":
        pushstore.delete(body.endpoint)
        raise HTTPException(status_code=410, detail="The browser has unsubscribed")
    if result != "ok":
        raise HTTPException(status_code=502, detail="The push service did not accept the message")
    return {"sent": True}
