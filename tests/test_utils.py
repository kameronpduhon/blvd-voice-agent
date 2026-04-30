from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.utils import (
    compress_days,
    detect_time_window,
    extract_zip,
    format_hours,
    resolve_template,
)

# --- extract_zip ---


def test_extract_zip_from_full_address():
    assert extract_zip("456 Cypress St Springfield 12345") == "12345"


def test_extract_zip_from_address_with_comma():
    assert extract_zip("456 Cypress St, Springfield, IL 12345") == "12345"


def test_extract_zip_five_digit():
    assert extract_zip("123 Main St 12347") == "12347"


def test_extract_zip_none_found():
    assert extract_zip("123 Main St Springfield") is None


def test_extract_zip_zip_plus_four():
    assert extract_zip("456 Cypress St 12345-1234") == "12345"


# --- resolve_template ---


def test_resolve_template_single_field():
    result = resolve_template("Hello {name}", {"name": "Eric"})
    assert result == "Hello Eric"


def test_resolve_template_multiple_fields():
    result = resolve_template(
        "Technician at {appointment_time} for {name}",
        {"appointment_time": "tomorrow 9am", "name": "Eric"},
    )
    assert result == "Technician at tomorrow 9am for Eric"


def test_resolve_template_no_placeholders():
    result = resolve_template("No placeholders here", {"name": "Eric"})
    assert result == "No placeholders here"


def test_resolve_template_unresolved_placeholder():
    result = resolve_template(
        "Hello {name}, your time is {appointment_time}", {"name": "Eric"}
    )
    assert result == "Hello Eric, your time is {appointment_time}"


# --- detect_time_window ---


PLAYBOOK_HOURS = {
    "meta": {"timezone": "America/Chicago"},
    "hours": {
        "office": {
            "start": "08:00",
            "end": "17:00",
            "days": ["mon", "tue", "wed", "thu", "fri"],
        },
        "on_call": {"start": "17:00", "end": "22:00"},
    },
}


def _mock_now(year, month, day, hour, minute):
    tz = ZoneInfo("America/Chicago")
    return datetime(year, month, day, hour, minute, tzinfo=tz)


def test_detect_office_hours_weekday():
    with patch("src.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(2026, 3, 18, 10, 0)  # Wed 10am
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert detect_time_window(PLAYBOOK_HOURS) == "office_hours"


def test_detect_on_call_hours():
    with patch("src.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(2026, 3, 18, 18, 0)  # Wed 6pm
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert detect_time_window(PLAYBOOK_HOURS) == "on_call"


def test_detect_after_hours():
    with patch("src.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(2026, 3, 18, 23, 0)  # Wed 11pm
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert detect_time_window(PLAYBOOK_HOURS) == "after_hours"


PLAYBOOK_OVERNIGHT_ON_CALL = {
    "meta": {"timezone": "America/Chicago"},
    "hours": {
        "office": {
            "start": "08:00",
            "end": "17:00",
            "days": ["mon", "tue", "wed", "thu", "fri"],
        },
        "on_call": {"start": "17:00", "end": "06:00"},
    },
}


def test_detect_on_call_overnight_evening():
    """On-call window 17:00-06:00: 9pm should be on_call."""
    with patch("src.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(2026, 3, 18, 21, 0)  # Wed 9pm
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert detect_time_window(PLAYBOOK_OVERNIGHT_ON_CALL) == "on_call"


def test_detect_on_call_overnight_early_morning():
    """On-call window 17:00-06:00: 3am should be on_call."""
    with patch("src.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(2026, 3, 19, 3, 0)  # Thu 3am
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert detect_time_window(PLAYBOOK_OVERNIGHT_ON_CALL) == "on_call"


def test_detect_on_call_overnight_after_end():
    """On-call window 17:00-06:00: 7am should NOT be on_call."""
    with patch("src.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(2026, 3, 19, 7, 0)  # Thu 7am
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert detect_time_window(PLAYBOOK_OVERNIGHT_ON_CALL) != "on_call"


def test_detect_weekend_not_office():
    with patch("src.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(2026, 3, 21, 10, 0)  # Sat 10am
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert detect_time_window(PLAYBOOK_HOURS) != "office_hours"


# --- compress_days / format_hours ---


def test_compress_days_weekdays():
    assert compress_days(["mon", "tue", "wed", "thu", "fri"]) == "Mon-Fri"


def test_compress_days_all_week():
    assert compress_days(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]) == "Mon-Sun"


def test_compress_days_single():
    assert compress_days(["mon"]) == "Mon"


def test_format_hours_office():
    hours = {
        "start": "08:00",
        "end": "17:00",
        "days": ["mon", "tue", "wed", "thu", "fri"],
    }
    assert format_hours(hours) == "Mon-Fri 8am-5pm"


def test_format_hours_on_call():
    hours = {"start": "17:00", "end": "22:00"}
    result = format_hours(hours)
    assert "5pm" in result
    assert "10pm" in result
