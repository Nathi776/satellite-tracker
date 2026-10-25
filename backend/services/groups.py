"""Satellite groups (Stations, Africa, Weather ...) worked out from the satellite's name.

CelesTrak's "active" TLE file contains names but no category, so this is a heuristic:
good enough to filter and colour a map, not an authoritative catalogue. Each satellite
belongs to exactly ONE group; when several would match, the earlier entry in GROUPS wins
(so NILESAT is "Africa", not "Comms").
"""
import re

from backend import config

# id, label, regex matched against the upper-case name (None = special handling)
GROUPS = [
    ("stations", "Stations",
     r"^(ISS|CSS)\b|PROGRESS|SOYUZ[- ]?MS|TIANZHOU|SHENZHOU|CYGNUS|CREW DRAGON|CARGO DRAGON|^DRAGON|^HTV"),
    ("africa", "Africa", None),
    ("weather", "Weather",
     r"^(NOAA|GOES|METEOSAT|METOP|FENGYUN|FY-|METEOR-M|DMSP|HIMAWARI|ELEKTRO|SUOMI NPP|JPSS|INSAT|"
     r"GOMS|MTSAT|COMS|GK-2A|ARKTIKA|MSG-)"),
    ("navigation", "Navigation",
     r"NAVSTAR|^GPS |GLONASS|GALILEO|^GSAT0|BEIDOU|^QZS|IRNSS|NAVIC"),
    ("starlink", "Starlink", r"^STARLINK"),
    ("oneweb", "OneWeb", r"^ONEWEB"),
    ("comms", "Comms",
     r"IRIDIUM|GLOBALSTAR|ORBCOMM|INTELSAT|EUTELSAT|^SES-|^ASTRA|TELESAT|^ANIK|ARABSAT|THURAYA|"
     r"INMARSAT|VIASAT|^O3B|SKYNET|^TDRS|AMAZONAS|HISPASAT|YAMAL|^EXPRESS|TURKSAT|^AMOS|MEASAT|"
     r"APSTAR|ASIASAT|^JCSAT|ECHOSTAR|SIRIUS|TELSTAR|DIRECTV"),
]
OTHER = ("other", "Other")

_COMPILED = [(gid, re.compile(rx)) if rx else (gid, None) for gid, _label, rx in GROUPS]
LABELS = {gid: label for gid, label, _ in GROUPS}
LABELS[OTHER[0]] = OTHER[1]
ORDER = [gid for gid, _l, _r in GROUPS] + [OTHER[0]]


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _is_african(name: str) -> bool:
    squashed = _squash(name)
    return any(_squash(token) in squashed for token in config.AFRICA_NAME_TOKENS)


def classify(name: str) -> str:
    """Group id for a satellite name."""
    upper = name.upper()
    for gid, rx in _COMPILED:
        if gid == "africa":
            if _is_african(name):
                return gid
        elif rx.search(upper):
            return gid
    return OTHER[0]


def classify_all(names) -> dict:
    return {name: classify(name) for name in names}


def summarize(group_by_name: dict) -> list:
    """[{id, label, count}] in display order, including empty groups."""
    counts = dict.fromkeys(ORDER, 0)
    for gid in group_by_name.values():
        counts[gid] = counts.get(gid, 0) + 1
    return [{"id": gid, "label": LABELS[gid], "count": counts[gid]} for gid in ORDER]
