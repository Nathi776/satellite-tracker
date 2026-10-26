"""Which satellites belong to African countries, and which country.

CelesTrak's TLE feed has no operator or country field, so this is a name table. Each entry is
a name *prefix* (case and punctuation ignored) matched at the start of any word, so "TIBA1" matches
"TIBA-1" but "ALSAT" does not match "GALSAT". The table was written from memory of how these
satellites are named in public catalogues and could not be checked against the live feed:
use `GET /africa` (its `unmatched` list) to see which entries match nothing today, and extend
`EXTRA_ENTRIES` in backend/config.py for anything missing.
"""
import re

from backend import config

# (name prefix, country). First match wins.
ENTRIES = [
    # South Africa
    ("ZACUBE", "South Africa"), ("TSHEPISOSAT", "South Africa"), ("SUMBANDILA", "South Africa"),
    ("MDASAT", "South Africa"), ("NSIGHT", "South Africa"),
    # Nigeria
    ("NIGERIA", "Nigeria"), ("NIGCOMSAT", "Nigeria"),
    # Egypt
    ("EGYPTSAT", "Egypt"), ("MISRSAT", "Egypt"), ("NILESAT", "Egypt"), ("TIBA1", "Egypt"),
    # North Africa
    ("ALSAT", "Algeria"), ("ALCOMSAT", "Algeria"),
    ("MOHAMMED VI", "Morocco"), ("MOROCCO", "Morocco"),
    ("TUNISIA", "Tunisia"), ("CHALLENGE ONE", "Tunisia"),
    ("SUDANSAT", "Sudan"),
    # East Africa
    ("ETRSS", "Ethiopia"), ("ETHIOPIA", "Ethiopia"),
    ("1KUNS", "Kenya"), ("KENYA", "Kenya"), ("TAIFA", "Kenya"),
    ("RWASAT", "Rwanda"), ("RWANDA", "Rwanda"),
    ("UGANDA", "Uganda"), ("PEARLAFRICASAT", "Uganda"),
    ("MAURITIUS", "Mauritius"),
    # West / Central / Southern Africa
    ("GHANASAT", "Ghana"), ("GHANA", "Ghana"),
    ("GAINDESAT", "Senegal"),
    ("ANGOSAT", "Angola"),
    ("ZIMSAT", "Zimbabwe"),
    ("BOTSWANA", "Botswana"), ("BOTSAT", "Botswana"),
    ("LESOTHO", "Lesotho"),
    # Pan-African operators
    ("RASCOM", "Pan-African"), ("AFRICASAT", "Pan-African"), ("AFRISTAR", "Pan-African"),
]


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _pattern(prefix: str):
    chars = _squash(prefix)
    return re.compile(r"(?<![a-z0-9])" + r"[\W_]*".join(re.escape(c) for c in chars))


def _compiled():
    extra = [(p, c) for p, c in getattr(config, "EXTRA_ENTRIES", [])]
    return [(prefix, country, _pattern(prefix)) for prefix, country in ENTRIES + extra]


def country_of(name: str):
    """Country (or "Pan-African") for a satellite name, or None."""
    lowered = name.lower()
    for _prefix, country, rx in _compiled():
        if rx.search(lowered):
            return country
    return None


def is_african(name: str) -> bool:
    return country_of(name) is not None


def unmatched_entries(names) -> list:
    """Table entries that match none of `names` (a hint that a name is wrong or decayed)."""
    lowered = [n.lower() for n in names]
    return [
        {"prefix": prefix, "country": country}
        for prefix, country, rx in _compiled()
        if not any(rx.search(n) for n in lowered)
    ]
