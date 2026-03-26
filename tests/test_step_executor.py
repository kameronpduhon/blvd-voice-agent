from unittest.mock import AsyncMock

import pytest

from src import actions
from src.step_executor import StepExecutor


# Register a test version of check_fee_approved for the consecutive actions test
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
    "service_areas": ["70502"],
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
    "service_areas": ["70502"],
    "scripts": {"closing_booked": "Done.", "closing_message": "Done."},
}


# --- constructor and first step tests ---


@pytest.mark.asyncio
async def test_constructor_sets_intent_and_dispatches_first_collect():
    executor = StepExecutor(MINIMAL_PLAYBOOK, "routine_service")
    session = make_mock_session()
    result = await executor._dispatch_current_step(session)
    assert "Ask for name." in result
    assert executor.current_intent == "routine_service"
    assert executor.current_step_index == 0


@pytest.mark.asyncio
async def test_constructor_with_speak_first_step():
    executor = StepExecutor(PLAYBOOK_WITH_SPEAK, "test_intent")
    session = make_mock_session()
    result = await executor._dispatch_current_step(session)
    assert 'Say EXACTLY: "Fee is $89."' in result
    assert "Confirm fee." in result
    assert executor.current_step_index == 1


# --- update_field tests ---


@pytest.mark.asyncio
async def test_update_field_stores_value_and_advances():
    executor = StepExecutor(MINIMAL_PLAYBOOK, "routine_service")
    session = make_mock_session()
    result = await executor.update_field("name", "Eric Tails", session)
    assert executor.collected["name"] == "Eric Tails"
    assert result == "Ask for phone."


@pytest.mark.asyncio
async def test_update_field_rejects_wrong_field():
    executor = StepExecutor(MINIMAL_PLAYBOOK, "routine_service")
    session = make_mock_session()
    result = await executor.update_field("phone", "555-1234", session)
    assert "name" in result.lower()


@pytest.mark.asyncio
async def test_update_field_rejects_placeholder():
    executor = StepExecutor(MINIMAL_PLAYBOOK, "routine_service")
    session = make_mock_session()
    result = await executor.update_field("name", "[Name]", session)
    assert "placeholder" in result.lower() or "real" in result.lower()


@pytest.mark.asyncio
async def test_update_field_rejects_empty_string():
    """KAM-19: Empty string from preemptive generation must be rejected."""
    executor = StepExecutor(MINIMAL_PLAYBOOK, "routine_service")
    session = make_mock_session()
    result = await executor.update_field("name", "", session)
    assert "real value" in result.lower()
    assert executor.current_step_index == 0  # did not advance


@pytest.mark.asyncio
async def test_update_field_rejects_whitespace_only():
    """KAM-19: Whitespace-only string must also be rejected."""
    executor = StepExecutor(MINIMAL_PLAYBOOK, "routine_service")
    session = make_mock_session()
    result = await executor.update_field("name", "   ", session)
    assert "real value" in result.lower()
    assert executor.current_step_index == 0


# --- deliver_speak tests ---


@pytest.mark.asyncio
async def test_verbatim_speak_with_collect_lookahead():
    executor = StepExecutor(PLAYBOOK_WITH_SPEAK, "test_intent")
    session = make_mock_session()
    result = await executor._dispatch_current_step(session)
    session.say.assert_not_called()
    assert 'Say EXACTLY: "Fee is $89."' in result
    assert "Confirm fee." in result
    assert executor.current_step_index == 1


@pytest.mark.asyncio
async def test_guided_speak_with_collect_lookahead():
    executor = StepExecutor(PLAYBOOK_GUIDED_SPEAK, "test_intent")
    session = make_mock_session()
    result = await executor._dispatch_current_step(session)
    session.say.assert_not_called()
    assert "Greet the caller warmly." in result
    assert "Ask for name." in result
    assert executor.current_step_index == 1


# --- edge cases ---


@pytest.mark.asyncio
async def test_verbatim_speak_no_lookahead():
    """Verbatim speak with no following collect returns Say EXACTLY."""
    executor = StepExecutor(PLAYBOOK_VERBATIM_SPEAK_ALONE, "test_intent")
    session = make_mock_session()
    result = await executor._dispatch_current_step(session)
    session.say.assert_not_called()
    assert 'Say EXACTLY: "Goodbye."' in result


@pytest.mark.asyncio
async def test_guided_speak_no_lookahead():
    """Guided speak without following collect returns prompt without Say EXACTLY."""
    executor = StepExecutor(PLAYBOOK_GUIDED_SPEAK_ALONE, "test_intent")
    session = make_mock_session()
    result = await executor._dispatch_current_step(session)
    session.say.assert_not_called()
    assert "Let the caller know you'll take a message." in result
    assert "Say EXACTLY" not in result


@pytest.mark.asyncio
async def test_guided_speak_with_collect_no_say_exactly():
    """Guided speak with collect lookahead should NOT include Say EXACTLY."""
    executor = StepExecutor(PLAYBOOK_GUIDED_SPEAK, "test_intent")
    session = make_mock_session()
    result = await executor._dispatch_current_step(session)
    assert "Say EXACTLY" not in result
    assert "Greet the caller warmly." in result
    assert "Ask for name." in result


@pytest.mark.asyncio
async def test_advance_past_end_returns_call_ended():
    """advance() past the last step returns [call_ended]."""
    executor = StepExecutor(MINIMAL_PLAYBOOK, "routine_service")
    session = make_mock_session()
    await executor.update_field("name", "Eric", session)
    result = await executor.update_field("phone", "555-1234", session)
    assert result == "[call_ended]"


@pytest.mark.asyncio
async def test_consecutive_actions_recurse_correctly():
    """Consecutive action steps recurse through advance().
    update_field stores "yes" -> advance -> check_fee_approved (action) sees "yes" -> advance -> collect name
    """
    executor = StepExecutor(PLAYBOOK_CONSECUTIVE_ACTIONS, "test_intent")
    session = make_mock_session()
    result = await executor.update_field("fee_approved", "yes", session)
    assert result == "Ask for name."


@pytest.mark.asyncio
async def test_emergency_full_flow():
    """Emergency: collect name/phone/address -> confirm -> dispatch."""
    executor = StepExecutor(PLAYBOOK_EMERGENCY, "emergency")
    session = make_mock_session()

    result = await executor._dispatch_current_step(session)
    assert "Ask for name." in result

    result = await executor.update_field("name", "Eric Tails", session)
    assert result == "Ask for phone."

    result = await executor.update_field("phone", "337-232-2341", session)
    assert result == "Ask for address."

    result = await executor.update_field("address", "456 Cypress St 70502", session)
    assert result == "Confirm dispatch."

    result = await executor.update_field("emergency_confirmed", "yes", session)
    assert "[call_ended]" in result
    assert executor.outcome == "dispatched"


@pytest.mark.asyncio
async def test_emergency_confirmed_no_takes_message():
    """When caller says no at confirmation, take a message and end the call."""
    executor = StepExecutor(PLAYBOOK_EMERGENCY, "emergency")
    session = make_mock_session()

    await executor.update_field("name", "Eric Tails", session)
    await executor.update_field("phone", "337-232-2341", session)
    await executor.update_field("address", "456 Cypress St 70502", session)

    result = await executor.update_field("emergency_confirmed", "no", session)
    assert "[call_ended]" in result
    assert executor.outcome == "message_taken"


@pytest.mark.asyncio
async def test_cancellation_full_flow():
    """Cancellation: collect name/phone/reason -> take_message."""
    executor = StepExecutor(PLAYBOOK_CANCELLATION, "cancellation")
    session = make_mock_session()

    result = await executor._dispatch_current_step(session)
    assert "Ask for name." in result

    result = await executor.update_field("name", "Eric Tails", session)
    assert result == "Ask for phone."

    result = await executor.update_field("phone", "337-232-2341", session)
    assert result == "Ask reason."

    result = await executor.update_field(
        "cancellation_reason", "Changed my mind", session
    )
    assert "[call_ended]" in result
    assert executor.outcome == "message_taken"


@pytest.mark.asyncio
async def test_warranty_speak_then_collect():
    """Warranty intent: speak verbatim warranty text, then collect name (lookahead merge)."""
    executor = StepExecutor(PLAYBOOK_WARRANTY, "warranty")
    session = make_mock_session()

    result = await executor._dispatch_current_step(session)
    assert 'Say EXACTLY: "All work has a one-year warranty."' in result
    assert "Ask for name." in result
    assert executor.current_step_index == 1  # Lookahead advanced past speak


# --- pre_collected tests ---


@pytest.mark.asyncio
async def test_pre_collected_skips_matching_steps():
    """Pre-collected fields skip corresponding collect steps at the start."""
    executor = StepExecutor(
        MINIMAL_PLAYBOOK, "routine_service", pre_collected={"name": "Eric Tails"}
    )
    session = make_mock_session()
    assert executor.current_step_index == 1
    assert executor.collected["name"] == "Eric Tails"
    result = await executor._dispatch_current_step(session)
    assert result == "Ask for phone."


@pytest.mark.asyncio
async def test_pre_collected_skips_multiple_steps():
    """Pre-collected name and phone skips both collect steps."""
    executor = StepExecutor(
        MINIMAL_PLAYBOOK,
        "routine_service",
        pre_collected={"name": "Eric Tails", "phone": "555-1234"},
    )
    assert executor.current_step_index == 2
    assert executor.collected["name"] == "Eric Tails"
    assert executor.collected["phone"] == "555-1234"


@pytest.mark.asyncio
async def test_pre_collected_only_skips_consecutive_from_start():
    """Pre-collected stops at the first non-matching step."""
    # phone is step 1, but name (step 0) is not pre-collected
    executor = StepExecutor(
        MINIMAL_PLAYBOOK, "routine_service", pre_collected={"phone": "555-1234"}
    )
    # Should NOT skip step 0 (name) even though phone is pre-collected
    assert executor.current_step_index == 0


@pytest.mark.asyncio
async def test_pre_collected_none_starts_at_zero():
    """No pre_collected starts at step 0."""
    executor = StepExecutor(MINIMAL_PLAYBOOK, "routine_service")
    assert executor.current_step_index == 0
    assert executor.collected == {}


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


# --- incomplete appointment time tests ---


@pytest.mark.asyncio
async def test_appointment_time_rejects_day_only():
    """update_field rejects 'Friday' alone for appointment_time."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT, "routine_service")
    session = make_mock_session()
    await executor.update_field("name", "Eric Tails", session)
    result = await executor.update_field("appointment_time", "Friday", session)
    assert "appointment_time" not in executor.collected
    assert "time" in result.lower()
    assert "Friday" in result


@pytest.mark.asyncio
async def test_appointment_time_rejects_tomorrow():
    """update_field rejects 'tomorrow' alone for appointment_time."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT, "routine_service")
    session = make_mock_session()
    await executor.update_field("name", "Eric Tails", session)
    result = await executor.update_field("appointment_time", "tomorrow", session)
    assert "appointment_time" not in executor.collected
    assert "time" in result.lower()


@pytest.mark.asyncio
async def test_appointment_time_accepts_day_and_time():
    """update_field accepts 'Friday at 2 PM' — complete appointment time."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT, "routine_service")
    session = make_mock_session()
    await executor.update_field("name", "Eric Tails", session)
    result = await executor.update_field("appointment_time", "Friday at 2 PM", session)
    assert executor.collected["appointment_time"] == "Friday at 2 PM"


@pytest.mark.asyncio
async def test_appointment_time_accepts_tomorrow_morning():
    """update_field accepts 'tomorrow morning' — not just a bare day name."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT, "routine_service")
    session = make_mock_session()
    await executor.update_field("name", "Eric Tails", session)
    result = await executor.update_field(
        "appointment_time", "tomorrow morning", session
    )
    assert executor.collected["appointment_time"] == "tomorrow morning"


@pytest.mark.asyncio
async def test_appointment_time_step_does_not_advance_on_reject():
    """Rejecting incomplete appointment_time keeps step index on the same step."""
    executor = StepExecutor(PLAYBOOK_WITH_APPOINTMENT, "routine_service")
    session = make_mock_session()
    await executor.update_field("name", "Eric Tails", session)
    assert executor.current_step_index == 1  # on appointment_time
    await executor.update_field("appointment_time", "Monday", session)
    assert executor.current_step_index == 1  # still on appointment_time
