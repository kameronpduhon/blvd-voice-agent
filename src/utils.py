import re
from datetime import datetime
from zoneinfo import ZoneInfo


def extract_zip(address: str) -> str | None:
    """Extract 5-digit US zip code from an address string."""
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", address)
    return match.group(1) if match else None


def resolve_template(template: str, collected: dict) -> str:
    """Replace {field_name} placeholders with values from collected dict."""
    resolved = template
    for field, value in collected.items():
        resolved = resolved.replace(f"{{{field}}}", value)
    return resolved


def detect_time_window(playbook: dict) -> str:
    """Determine current time window based on playbook hours config."""
    tz = ZoneInfo(playbook["meta"]["timezone"])
    now = datetime.now(tz)
    day = now.strftime("%a").lower()[:3]
    current_time = now.strftime("%H:%M")

    office = playbook["hours"]["office"]
    if day in office["days"] and office["start"] <= current_time < office["end"]:
        return "office_hours"

    on_call = playbook["hours"].get("on_call")
    if on_call and on_call["start"] <= current_time < on_call["end"]:
        return "on_call"
    # TODO: handle on-call hours that span midnight (e.g., 17:00-06:00).
    # Current comparison breaks when end < start. Fine for Acme HVAC (ends 22:00)
    # but will need fixing when clients have overnight on-call windows.

    return "after_hours"


DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_LABELS = {
    "mon": "Mon",
    "tue": "Tue",
    "wed": "Wed",
    "thu": "Thu",
    "fri": "Fri",
    "sat": "Sat",
    "sun": "Sun",
}


def compress_days(days: list[str]) -> str:
    """Compress day list into ranges like 'Mon-Fri'."""
    if not days:
        return ""
    indices = sorted(DAY_ORDER.index(d) for d in days)
    ranges = []
    start = indices[0]
    end = indices[0]
    for i in indices[1:]:
        if i == end + 1:
            end = i
        else:
            ranges.append((start, end))
            start = i
            end = i
    ranges.append((start, end))
    parts = []
    for s, e in ranges:
        if s == e:
            parts.append(DAY_LABELS[DAY_ORDER[s]])
        else:
            parts.append(f"{DAY_LABELS[DAY_ORDER[s]]}-{DAY_LABELS[DAY_ORDER[e]]}")
    return ", ".join(parts)


def _format_time(t: str) -> str:
    """Convert '08:00' to '8am', '17:00' to '5pm'."""
    hour, minute = int(t.split(":")[0]), int(t.split(":")[1])
    suffix = "am" if hour < 12 else "pm"
    if hour == 0:
        hour = 12
    elif hour > 12:
        hour -= 12
    if minute == 0:
        return f"{hour}{suffix}"
    return f"{hour}:{minute:02d}{suffix}"


def format_hours(hours: dict) -> str:
    """Format hours dict to readable string like 'Mon-Fri 8am-5pm'."""
    start = _format_time(hours["start"])
    end = _format_time(hours["end"])
    days = hours.get("days")
    if days:
        return f"{compress_days(days)} {start}-{end}"
    return f"{start}-{end}"
