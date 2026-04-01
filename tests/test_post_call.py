from unittest.mock import AsyncMock, patch

import pytest

from src.post_call import post_summary_from_userdata


def _make_userdata(**overrides):
    """Build a minimal userdata dict for testing."""
    base = {
        "intent": "routine_service",
        "requested_intent": None,
        "time_window": "office_hours",
        "collected": {"phone": "337-232-2341", "name": "Eric Tails"},
        "transcript": "Agent: Hello\nCaller: Hi\n",
        "outcome": "booked",
        "sip_caller_number": "+13375551234",
        "sip_dnis": "+13372707004",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_payload_contains_all_expected_fields():
    """Verify all expected fields are present in the post payload."""
    userdata = _make_userdata()
    with patch("src.post_call.aiohttp.ClientSession") as mock_session_cls:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = AsyncMock()
        mock_http = AsyncMock()
        mock_http.post.return_value.__aenter__.return_value = mock_resp
        mock_session_cls.return_value.__aenter__.return_value = mock_http

        await post_summary_from_userdata(userdata, 1000.0, 1060.0)

        call_args = mock_http.post.call_args
        payload = call_args.kwargs["json"]
        expected_keys = {
            "caller_number", "callback_number", "dnis", "intent",
            "requested_intent", "outcome", "collected", "transcript",
            "duration_seconds", "time_window",
        }
        assert expected_keys == set(payload.keys())


@pytest.mark.asyncio
async def test_caller_number_uses_sip_ani():
    """KAM-28: caller_number should be SIP ANI, not collected phone."""
    userdata = _make_userdata(
        sip_caller_number="+13375551234",
        collected={"phone": "337-232-2341"},
    )
    with patch("src.post_call.aiohttp.ClientSession") as mock_session_cls:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = AsyncMock()
        mock_http = AsyncMock()
        mock_http.post.return_value.__aenter__.return_value = mock_resp
        mock_session_cls.return_value.__aenter__.return_value = mock_http

        await post_summary_from_userdata(userdata, 1000.0, 1060.0)

        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["caller_number"] == "+13375551234"
        assert payload["callback_number"] == "337-232-2341"


@pytest.mark.asyncio
async def test_caller_number_falls_back_to_collected_phone():
    """When no SIP metadata, caller_number should fall back to collected phone."""
    userdata = _make_userdata(
        sip_caller_number="",
        collected={"phone": "337-232-2341"},
    )
    with patch("src.post_call.aiohttp.ClientSession") as mock_session_cls:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = AsyncMock()
        mock_http = AsyncMock()
        mock_http.post.return_value.__aenter__.return_value = mock_resp
        mock_session_cls.return_value.__aenter__.return_value = mock_http

        await post_summary_from_userdata(userdata, 1000.0, 1060.0)

        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["caller_number"] == "337-232-2341"


@pytest.mark.asyncio
async def test_duration_uses_hangup_time():
    """KAM-30: Duration should use hangup_time, not current time."""
    userdata = _make_userdata()
    with patch("src.post_call.aiohttp.ClientSession") as mock_session_cls:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = AsyncMock()
        mock_http = AsyncMock()
        mock_http.post.return_value.__aenter__.return_value = mock_resp
        mock_session_cls.return_value.__aenter__.return_value = mock_http

        await post_summary_from_userdata(userdata, 1000.0, 1060.0)

        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["duration_seconds"] == 60


@pytest.mark.asyncio
async def test_backend_url_read_lazily():
    """KAM-26: BACKEND_URL should be read at call time, not import time."""
    userdata = _make_userdata()
    with (
        patch("src.post_call.os.environ.get", return_value="http://prod.example.com") as mock_env,
        patch("src.post_call.aiohttp.ClientSession") as mock_session_cls,
    ):
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = AsyncMock()
        mock_http = AsyncMock()
        mock_http.post.return_value.__aenter__.return_value = mock_resp
        mock_session_cls.return_value.__aenter__.return_value = mock_http

        await post_summary_from_userdata(userdata, 1000.0, 1060.0)

        mock_env.assert_called_once_with("BACKEND_URL", "http://localhost:8000")
        call_url = mock_http.post.call_args.args[0]
        assert call_url == "http://prod.example.com/api/call/summary"


@pytest.mark.asyncio
async def test_graceful_without_sip_metadata():
    """Console testing: no SIP metadata keys at all should not crash."""
    userdata = {
        "intent": "routine_service",
        "requested_intent": None,
        "time_window": "office_hours",
        "collected": {"phone": "337-232-2341"},
        "transcript": "",
        "outcome": "booked",
        # No sip_caller_number or sip_dnis keys
    }
    with patch("src.post_call.aiohttp.ClientSession") as mock_session_cls:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = AsyncMock()
        mock_http = AsyncMock()
        mock_http.post.return_value.__aenter__.return_value = mock_resp
        mock_session_cls.return_value.__aenter__.return_value = mock_http

        await post_summary_from_userdata(userdata, 1000.0, 1060.0)

        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["caller_number"] == "337-232-2341"
        assert payload["dnis"] == ""
