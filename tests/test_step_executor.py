from unittest.mock import AsyncMock

import pytest

from src import actions
from src.step_executor import StepExecutor


# Register test action stubs
async def _test_check_fee_approved(executor, session):
    if executor.collected.get("fee_approved", "").lower() in ("no", "n", "decline"):
        executor.outcome = "declined"
        return "[call_ended]"
    return await executor.advance(session)


actions.ACTION_REGISTRY["check_fee_approved"] = _test_check_fee_approved


async def _test_check_emergency_confirmed(executor, session):
    confirmed = executor.collected.get("emergency_confirmed", "").lower()
    if confirmed in ("no", "n", "nope", "not yet", "hold on", "wait"):
        return await _test_take_message(executor, session)
    return await executor.advance(session)


async def _test_dispatch_oncall_tech(executor, session):
    executor.outcome = "dispatched"
    return 'Say EXACTLY: "Tech dispatched." [call_ended]'


async def _test_take_message(executor, session):
    executor.outcome = "message_taken"
    return 'Say EXACTLY: "Message taken. Goodbye." [call_ended]'


actions.ACTION_REGISTRY["check_emergency_confirmed"] = _test_check_emergency_confirmed
actions.ACTION_REGISTRY["dispatch_oncall_tech"] = _test_dispatch_oncall_tech
actions.ACTION_REGISTRY["take_message"] = _test_take_message


def make_mock_session():
    session = AsyncMock()
    session.say = AsyncMock()
    session.generate_reply = AsyncMock()
    return session


MINIMAL_PLAYBOOK = {
    "intents": {
        "routine_service": {
            "label": "Routine Service",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
                {
                    "type": "collect",
                    "field": "phone",
                    "mode": "guided",
                    "prompt": "Ask for phone.",
                },
            ],
        },
        "_fallback": {
            "label": "Take a Message",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
            ],
        },
    },
    "service_areas": ["12345"],
    "scripts": {
        "closing_booked": "You're all set for {appointment_time}.",
        "closing_message": "Message taken for {name}. Goodbye.",
    },
}

PLAYBOOK_WITH_SPEAK = {
    "intents": {
        "test_intent": {
            "label": "Test",
            "steps": [
                {"type": "speak", "mode": "verbatim", "text": "Fee is $89."},
                {
                    "type": "collect",
                    "field": "fee_approved",
                    "mode": "guided",
                    "prompt": "Confirm fee.",
                },
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                },
            ],
        },
    },
    "service_areas": [],
    "scripts": {},
}

PLAYBOOK_GUIDED_SPEAK = {
    "intents": {
        "test_intent": {
            "label": "Test",
            "steps": [
                {
                    "type": "speak",
                    "mode": "guided",
                    "prompt": "Greet the caller warmly.",
                },
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                },
            ],
        },
    },
    "service_areas": [],
    "scripts": {},
}

PLAYBOOK_VERBATIM_SPEAK_ALONE = {
    "intents": {
        "test_intent": {
            "label": "Test",
            "steps": [
                {"type": "speak", "mode": "verbatim", "text": "Goodbye."},
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                },
            ],
        },
    },
    "service_areas": [],
    "scripts": {},
}

PLAYBOOK_GUIDED_SPEAK_ALONE = {
    "intents": {
        "test_intent": {
            "label": "Test",
            "steps": [
                {
                    "type": "speak",
                    "mode": "guided",
                    "prompt": "Let the caller know you'll take a message.",
                },
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                },
            ],
        },
    },
    "service_areas": [],
    "scripts": {},
}

PLAYBOOK_EMERGENCY = {
    "intents": {
        "emergency": {
            "label": "Emergency Service",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
                {
                    "type": "collect",
                    "field": "phone",
                    "mode": "guided",
                    "prompt": "Ask for phone.",
                },
                {
                    "type": "collect",
                    "field": "address",
                    "mode": "guided",
                    "prompt": "Ask for address.",
                },
                {
                    "type": "collect",
                    "field": "emergency_confirmed",
                    "mode": "guided",
                    "prompt": "Confirm dispatch.",
                },
                {"type": "action", "fn": "check_emergency_confirmed"},
                {"type": "action", "fn": "dispatch_oncall_tech"},
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                }
            ],
        },
    },
    "service_areas": [],
    "scripts": {
        "closing_dispatched": "Tech sent.",
        "closing_message": "Message taken. Goodbye.",
    },
}

PLAYBOOK_CANCELLATION = {
    "intents": {
        "cancellation": {
            "label": "Cancel Appointment",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
                {
                    "type": "collect",
                    "field": "phone",
                    "mode": "guided",
                    "prompt": "Ask for phone.",
                },
                {
                    "type": "collect",
                    "field": "cancellation_reason",
                    "mode": "guided",
                    "prompt": "Ask reason.",
                },
                {"type": "action", "fn": "take_message"},
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                }
            ],
        },
    },
    "service_areas": [],
    "scripts": {"closing_message": "Message taken. Goodbye."},
}

PLAYBOOK_WARRANTY = {
    "intents": {
        "warranty": {
            "label": "Warranty Claim",
            "steps": [
                {
                    "type": "speak",
                    "mode": "verbatim",
                    "text": "All work has a one-year warranty.",
                },
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                }
            ],
        },
    },
    "service_areas": [],
    "scripts": {},
}

PLAYBOOK_CONSECUTIVE_ACTIONS = {
    "intents": {
        "test_intent": {
            "label": "Test",
            "steps": [
                {
                    "type": "collect",
                    "field": "fee_approved",
                    "mode": "guided",
                    "prompt": "Confirm fee.",
                },
                {"type": "action", "fn": "check_fee_approved"},
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                },
            ],
        },
    },
    "service_areas": ["12345"],
    "scripts": {"closing_booked": "Done.", "closing_message": "Done."},
}

PLAYBOOK_WITH_APPOINTMENT = {
    "intents": {
        "routine_service": {
            "label": "Routine Service",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
                {
                    "type": "collect",
                    "field": "appointment_time",
                    "mode": "guided",
                    "prompt": "Ask when they'd like to schedule.",
                },
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                },
            ],
        },
    },
    "service_areas": [],
    "scripts": {},
}

PLAYBOOK_WITH_AFTER_HOURS = {
    "intents": {
        "routine_service": {
            "label": "Routine Service",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
                {
                    "type": "collect",
                    "field": "phone",
                    "mode": "guided",
                    "prompt": "Ask for phone.",
                },
            ],
        },
        "emergency": {
            "label": "Emergency Service",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
                {
                    "type": "collect",
                    "field": "phone",
                    "mode": "guided",
                    "prompt": "Ask for phone.",
                },
                {"type": "action", "fn": "dispatch_oncall_tech"},
            ],
        },
        "cancellation": {
            "label": "Cancel Appointment",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                },
                {"type": "action", "fn": "take_message"},
            ],
        },
        "billing": {
            "label": "Billing Question",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                },
                {"type": "action", "fn": "take_message"},
            ],
        },
        "_after_hours": {
            "label": "After Hours Message",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask for name.",
                },
                {
                    "type": "collect",
                    "field": "phone",
                    "mode": "guided",
                    "prompt": "Ask for callback number.",
                },
                {"type": "action", "fn": "take_message"},
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Name?",
                },
            ],
        },
    },
    "service_areas": [],
    "scripts": {},
}


# --- set_intent tests ---


def test_set_intent_returns_first_step():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("routine_service", session)
    assert "Ask for name." in result
    assert executor.current_intent == "routine_service"
    assert executor.current_step_index == 0


def test_set_intent_with_speak_first_step():
    executor = StepExecutor(PLAYBOOK_WITH_SPEAK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("test_intent", session)
    assert 'Say EXACTLY: "Fee is $89."' in result
    assert "Confirm fee." in result
    assert executor.current_step_index == 1


def test_set_intent_unknown_falls_back():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("nonexistent", session)
    assert executor.current_intent == "_fallback"
    assert "Ask for name." in result


def test_set_intent_off_hours_redirects_to_after_hours():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "after_hours"
    session = make_mock_session()
    result = executor.set_intent("routine_service", session)
    assert executor.current_intent == "_after_hours"
    assert executor.requested_intent == "routine_service"
    assert "Ask for name." in result


def test_set_intent_emergency_bypasses_off_hours():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "after_hours"
    session = make_mock_session()
    result = executor.set_intent("emergency", session)
    assert executor.current_intent == "emergency"
    assert executor.requested_intent is None
    assert "Ask for name." in result


def test_set_intent_on_call_redirects_non_emergency():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "on_call"
    session = make_mock_session()
    executor.set_intent("billing", session)
    assert executor.current_intent == "_after_hours"
    assert executor.requested_intent == "billing"


def test_set_intent_office_hours_no_redirect():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    assert executor.current_intent == "routine_service"
    assert executor.requested_intent is None


def test_set_intent_clears_requested_intent_when_no_redirect():
    """requested_intent is explicitly None when no redirect happened."""
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    assert executor.requested_intent is None


# --- idle state (no intent) tests ---


@pytest.mark.asyncio
async def test_update_field_before_set_intent_returns_error():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    session = make_mock_session()
    result = await executor.update_field("name", "Eric Tails", session)
    assert "No intent" in result or "set_intent" in result


def test_current_steps_empty_when_no_intent():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    assert executor.current_steps == []


# --- switch_intent tests ---


def test_switch_intent_carries_shared_fields():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    executor.collected["name"] = "Eric Tails"
    executor.collected["phone"] = "555-100-4000"

    result = executor.switch_intent("cancellation", session)
    assert "Of course" in result
    assert executor.current_intent == "cancellation"
    assert executor.collected["name"] == "Eric Tails"
    assert executor.collected["phone"] == "555-100-4000"


def test_switch_intent_skips_pre_collected_steps():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    executor.collected["name"] = "Eric Tails"

    executor.switch_intent("cancellation", session)
    # cancellation steps: name → (skipped) → action take_message
    # With only name collected, should skip name step (index 0) → land on next uncollected
    assert executor.collected["name"] == "Eric Tails"
    assert executor.current_step_index > 0


def test_switch_intent_invalid_returns_error():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)

    result = executor.switch_intent("nonexistent", session)
    assert "Invalid intent" in result
    assert "routine_service" in result  # valid intents listed


def test_switch_intent_off_hours_redirects():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "after_hours"
    session = make_mock_session()
    executor.set_intent("emergency", session)
    executor.collected["name"] = "Eric Tails"
    executor.collected["phone"] = "555-100-4000"

    executor.switch_intent("cancellation", session)
    assert executor.current_intent == "_after_hours"
    assert executor.requested_intent == "cancellation"


def test_switch_intent_resets_outcome():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    executor.outcome = "booked"

    executor.switch_intent("cancellation", session)
    assert executor.outcome is None


def test_switch_intent_drops_non_shared_fields():
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    executor.collected["name"] = "Eric Tails"
    executor.collected["phone"] = "555-100-4000"
    executor.collected["address"] = "123 Main St 12345"

    executor.switch_intent("cancellation", session)
    assert "address" not in executor.collected
    assert "name" in executor.collected
    assert "phone" in executor.collected


def test_switch_intent_multiple_times():
    """switch_intent can be called more than once per call."""
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    executor.collected["name"] = "Eric Tails"

    executor.switch_intent("cancellation", session)
    assert executor.current_intent == "cancellation"

    executor.switch_intent("billing", session)
    assert executor.current_intent == "billing"
    assert executor.collected["name"] == "Eric Tails"


# --- update_field tests (with set_intent) ---


@pytest.mark.asyncio
async def test_update_field_stores_value_and_advances():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    result = await executor.update_field("name", "Eric Tails", session)
    assert executor.collected["name"] == "Eric Tails"
    assert result == "Ask for phone."


@pytest.mark.asyncio
async def test_update_field_rejects_wrong_field():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    result = await executor.update_field("phone", "555-1234", session)
    assert "name" in result.lower()


@pytest.mark.asyncio
async def test_update_field_rejects_placeholder():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    result = await executor.update_field("name", "[Name]", session)
    assert "placeholder" in result.lower() or "real" in result.lower()


@pytest.mark.asyncio
async def test_update_field_rejects_empty_string():
    """KAM-19: Empty string from preemptive generation must be rejected."""
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    result = await executor.update_field("name", "", session)
    assert "real value" in result.lower()
    assert executor.current_step_index == 0


@pytest.mark.asyncio
async def test_update_field_rejects_whitespace_only():
    """KAM-19: Whitespace-only string must also be rejected."""
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    result = await executor.update_field("name", "   ", session)
    assert "real value" in result.lower()
    assert executor.current_step_index == 0


# --- deliver_speak tests ---


@pytest.mark.asyncio
async def test_verbatim_speak_with_collect_lookahead():
    executor = StepExecutor(PLAYBOOK_WITH_SPEAK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("test_intent", session)
    # set_intent already dispatched first step and advanced index for speak+collect merge
    assert executor.current_step_index == 1


@pytest.mark.asyncio
async def test_guided_speak_with_collect_lookahead():
    executor = StepExecutor(PLAYBOOK_GUIDED_SPEAK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("test_intent", session)
    assert "Greet the caller warmly." in result
    assert "Ask for name." in result
    assert executor.current_step_index == 1


# --- edge cases ---


def test_verbatim_speak_no_lookahead():
    """Verbatim speak with no following collect returns Say EXACTLY."""
    executor = StepExecutor(PLAYBOOK_VERBATIM_SPEAK_ALONE)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("test_intent", session)
    assert 'Say EXACTLY: "Goodbye."' in result


def test_guided_speak_no_lookahead():
    """Guided speak without following collect returns prompt without Say EXACTLY."""
    executor = StepExecutor(PLAYBOOK_GUIDED_SPEAK_ALONE)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("test_intent", session)
    assert "Let the caller know you'll take a message." in result
    assert "Say EXACTLY" not in result


def test_guided_speak_with_collect_no_say_exactly():
    """Guided speak with collect lookahead should NOT include Say EXACTLY."""
    executor = StepExecutor(PLAYBOOK_GUIDED_SPEAK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("test_intent", session)
    assert "Say EXACTLY" not in result
    assert "Greet the caller warmly." in result
    assert "Ask for name." in result


@pytest.mark.asyncio
async def test_advance_past_end_returns_call_ended():
    """advance() past the last step returns [call_ended]."""
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    await executor.update_field("name", "Eric", session)
    result = await executor.update_field("phone", "555-1234", session)
    assert result == "[call_ended]"


@pytest.mark.asyncio
async def test_consecutive_actions_recurse_correctly():
    """Consecutive action steps recurse through advance()."""
    executor = StepExecutor(PLAYBOOK_CONSECUTIVE_ACTIONS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("test_intent", session)
    result = await executor.update_field("fee_approved", "yes", session)
    assert result == "Ask for name."


@pytest.mark.asyncio
async def test_emergency_full_flow():
    """Emergency: collect name/phone/address -> confirm -> dispatch."""
    executor = StepExecutor(PLAYBOOK_EMERGENCY)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("emergency", session)
    assert "Ask for name." in result

    result = await executor.update_field("name", "Eric Tails", session)
    assert result == "Ask for phone."

    result = await executor.update_field("phone", "555-100-4000", session)
    assert result == "Ask for address."

    result = await executor.update_field("address", "456 Cypress St 12345", session)
    assert result == "Confirm dispatch."

    result = await executor.update_field("emergency_confirmed", "yes", session)
    assert "[call_ended]" in result
    assert executor.outcome == "dispatched"


@pytest.mark.asyncio
async def test_emergency_confirmed_no_takes_message():
    """When caller says no at confirmation, take a message and end the call."""
    executor = StepExecutor(PLAYBOOK_EMERGENCY)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("emergency", session)

    await executor.update_field("name", "Eric Tails", session)
    await executor.update_field("phone", "555-100-4000", session)
    await executor.update_field("address", "456 Cypress St 12345", session)

    result = await executor.update_field("emergency_confirmed", "no", session)
    assert "[call_ended]" in result
    assert executor.outcome == "message_taken"


@pytest.mark.asyncio
async def test_cancellation_full_flow():
    """Cancellation: collect name/phone/reason -> take_message."""
    executor = StepExecutor(PLAYBOOK_CANCELLATION)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("cancellation", session)
    assert "Ask for name." in result

    result = await executor.update_field("name", "Eric Tails", session)
    assert result == "Ask for phone."

    result = await executor.update_field("phone", "555-100-4000", session)
    assert result == "Ask reason."

    result = await executor.update_field(
        "cancellation_reason", "Changed my mind", session
    )
    assert "[call_ended]" in result
    assert executor.outcome == "message_taken"


def test_warranty_speak_then_collect():
    """Warranty intent: speak verbatim warranty text, then collect name (lookahead merge)."""
    executor = StepExecutor(PLAYBOOK_WARRANTY)
    executor.time_window = "office_hours"
    session = make_mock_session()
    result = executor.set_intent("warranty", session)
    assert 'Say EXACTLY: "All work has a one-year warranty."' in result
    assert "Ask for name." in result
    assert executor.current_step_index == 1


# --- incomplete appointment time tests ---


@pytest.mark.asyncio
async def test_appointment_time_rejects_day_only():
    """update_field rejects 'Friday' alone for appointment_time."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    await executor.update_field("name", "Eric Tails", session)
    result = await executor.update_field("appointment_time", "Friday", session)
    assert "appointment_time" not in executor.collected
    assert "time" in result.lower()
    assert "Friday" in result


@pytest.mark.asyncio
async def test_appointment_time_rejects_tomorrow():
    """update_field rejects 'tomorrow' alone for appointment_time."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    await executor.update_field("name", "Eric Tails", session)
    result = await executor.update_field("appointment_time", "tomorrow", session)
    assert "appointment_time" not in executor.collected
    assert "time" in result.lower()


@pytest.mark.asyncio
async def test_appointment_time_accepts_day_and_time():
    """update_field accepts 'Friday at 2 PM' — complete appointment time."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    await executor.update_field("name", "Eric Tails", session)
    await executor.update_field("appointment_time", "Friday at 2 PM", session)
    assert executor.collected["appointment_time"] == "Friday at 2 PM"


@pytest.mark.asyncio
async def test_appointment_time_accepts_tomorrow_morning():
    """update_field accepts 'tomorrow morning' — not just a bare day name."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    await executor.update_field("name", "Eric Tails", session)
    await executor.update_field(
        "appointment_time", "tomorrow morning", session
    )
    assert executor.collected["appointment_time"] == "tomorrow morning"


@pytest.mark.asyncio
async def test_appointment_time_step_does_not_advance_on_reject():
    """Rejecting incomplete appointment_time keeps step index on the same step."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    await executor.update_field("name", "Eric Tails", session)
    assert executor.current_step_index == 1  # on appointment_time
    await executor.update_field("appointment_time", "Monday", session)
    assert executor.current_step_index == 1  # still on appointment_time


# --- overwrite previously collected field ---


@pytest.mark.asyncio
async def test_update_field_overwrite_previous():
    """Allow overwriting a previously collected field without advancing."""
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    executor.time_window = "office_hours"
    session = make_mock_session()
    executor.set_intent("routine_service", session)
    await executor.update_field("name", "Eric Tails", session)
    # Now on phone step — overwrite name
    result = await executor.update_field("name", "Eric Smith", session)
    assert executor.collected["name"] == "Eric Smith"
    assert "Updated name" in result
    assert executor.current_step_index == 1  # still on phone
