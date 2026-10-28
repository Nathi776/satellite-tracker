"""Orbital facts and a short description for one satellite."""
import math

from backend.services import africa
from backend.services import satellites as catalog
from backend.services.satellites import ts

MU_KM3_S2 = 398600.4418      # Earth's gravitational parameter
EQUATORIAL_RADIUS_KM = 6378.137

# Hand-written blurbs for a few well-known satellites, matched on the normalised name
# start. Everything else gets a description from its group (see GROUP_TEXT).
NAMED = [
    ("ISSZARYA", "The International Space Station: a crewed research laboratory built by NASA, "
                 "Roscosmos, ESA, JAXA and CSA. It circles the Earth about every 92 minutes."),
    ("CSSTIANHE", "Tianhe, the core module of China's Tiangong space station."),
    ("HST", "The Hubble Space Telescope, an orbiting observatory launched in 1990."),
    ("ZACUBE1", "South Africa's first CubeSat, built at the Cape Peninsula University of Technology "
                "and launched in 2013."),
]

GROUP_TEXT = {
    "stations": "A crewed or uncrewed space station, or a module of one.",
    "africa": "A satellite operated by an African country or organisation.",
    "weather": "A weather or Earth-observation satellite.",
    "navigation": "A satellite navigation (GNSS) satellite, such as GPS, Galileo, GLONASS or BeiDou.",
    "starlink": "Part of SpaceX's Starlink internet constellation in low Earth orbit.",
    "oneweb": "Part of the OneWeb broadband internet constellation.",
    "comms": "A communications satellite.",
    "other": "A satellite from the public CelesTrak catalogue. Its group is a guess from its name.",
}


def _norm(text: str) -> str:
    return "".join(c for c in text.upper() if c.isalnum())


def describe(name: str, group: str) -> str:
    n = _norm(name)
    for prefix, text in NAMED:
        if n.startswith(prefix):
            return text
    return GROUP_TEXT.get(group, GROUP_TEXT["other"])


def satellite_info(sat):
    """NORAD id, orbit shape and the age of the element set. None if the orbit is unusable."""
    m = sat.model
    n_rad_min = getattr(m, "no_kozai", 0.0)
    if not n_rad_min or n_rad_min <= 0:
        return None

    n_rad_s = n_rad_min / 60.0
    a_km = (MU_KM3_S2 / (n_rad_s ** 2)) ** (1.0 / 3.0)
    ecc = float(m.ecco)
    perigee = a_km * (1 - ecc) - EQUATORIAL_RADIUS_KM
    apogee = a_km * (1 + ecc) - EQUATORIAL_RADIUS_KM
    if any(math.isnan(v) for v in (perigee, apogee)):
        return None

    group = catalog.get_groups().get(sat.name, "other")
    now = ts.now()
    info = {
        "name": sat.name,
        "norad_id": int(m.satnum),
        "group": group,
        "country": africa.country_of(sat.name) if group == "africa" else None,
        "description": describe(sat.name, group),
        "inclination_deg": round(math.degrees(m.inclo), 2),
        "eccentricity": round(ecc, 6),
        "period_min": round(2 * math.pi / n_rad_min, 2),
        "revs_per_day": round(n_rad_min * 1440.0 / (2 * math.pi), 3),
        "perigee_km": round(perigee),
        "apogee_km": round(apogee),
        "epoch_utc": sat.epoch.utc_iso(),
        "element_age_days": round(float(now.tt - sat.epoch.tt), 2),
    }
    return info
