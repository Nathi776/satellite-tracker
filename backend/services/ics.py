"""Turn satellite passes into an iCalendar (.ics) file.

Phone and desktop calendars can then remind the user before a pass, with no push
infrastructure on our side. Each event carries a 10-minute alarm.
"""
from datetime import datetime, timezone


ALARM_MINUTES = 10
_STATUS_TEXT = {
    "visible": "Visible to the naked eye",
    "faint": "Too faint for the naked eye",
    "in_shadow": "In Earth's shadow",
    "daylight": "Sky too bright",
}


def _fmt(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    """RFC 5545: lines are at most 75 octets; continuation lines start with a space."""
    out, data = [], line.encode("utf-8")
    while len(data) > 75:
        cut = 75
        while cut > 0 and (data[cut] & 0xC0) == 0x80:  # don't split a multi-byte character
            cut -= 1
        out.append(data[:cut].decode("utf-8"))
        data = b" " + data[cut:]
    out.append(data.decode("utf-8"))
    return out


def passes_to_ics(passes: list[dict], lat: float, lon: float, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Satellite Tracker//Passes//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for p in passes:
        status = _STATUS_TEXT.get(p["visibility"], p["visibility"])
        detail = [
            status,
            f"{p['rise_direction']} to {p['set_direction']}, peaks at "
            f"{round(p['max_elevation_deg'])} deg in the {p['peak_direction']}",
        ]
        if p.get("visible_from_utc") and p.get("visible_until_utc"):
            detail.append(f"Visible {p['visible_from_utc'][11:16]}-{p['visible_until_utc'][11:16]} UTC")
        if p.get("magnitude") is not None:
            detail.append(f"Brightest about magnitude {p['magnitude']:.1f}")
        detail.append(f"Observer {lat:.3f}, {lon:.3f}. Times are estimates from public TLEs.")
        uid = f"{_fmt(p['rise_time_utc'])}-{_slug(p['name'])}@satellite-tracker"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_fmt(p['rise_time_utc'])}",
            f"DTEND:{_fmt(p['set_time_utc'])}",
            f"SUMMARY:{_escape(p['name'] + ' pass')}",
            f"DESCRIPTION:{_escape(chr(10).join(detail))}",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_escape(p['name'] + ' passes soon')}",
            f"TRIGGER:-PT{ALARM_MINUTES}M",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    folded = [part for line in lines for part in _fold(line)]
    return "\r\n".join(folded) + "\r\n"


def _slug(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
