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
    "scripts": {"closing_dispatched": "Tech sent.", "closing_message": "Message taken. Goodbye."},
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


# --- set_intent tests ---


@pytest.mark.asyncio
async def test_set_intent_returns_first_collect_prompt():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    session = make_mock_session()
    result = await executor.set_intent("routine_service", session)
    assert "Ask for name." in result
    assert executor.current_intent == "routine_service"
    assert executor.current_step_index == 0


@pytest.mark.asyncio
async def test_set_intent_unknown_routes_to_fallback():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    session = make_mock_session()
    await executor.set_intent("unknown_intent", session)
    assert executor.current_intent == "_fallback"


@pytest.mark.asyncio
async def test_set_intent_called_twice_returns_error():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    session = make_mock_session()
    await executor.set_intent("routine_service", session)
    result = await executor.set_intent("routine_service", session)
    assert "already been set" in result.lower()


# --- update_field tests ---


@pytest.mark.asyncio
async def test_update_field_stores_value_and_advances():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    session = make_mock_session()
    await executor.set_intent("routine_service", session)
    result = await executor.update_field("name", "Eric Tails", session)
    assert executor.collected["name"] == "Eric Tails"
    assert result == "Ask for phone."


@pytest.mark.asyncio
async def test_update_field_rejects_wrong_field():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    session = make_mock_session()
    await executor.set_intent("routine_service", session)
    result = await executor.update_field("phone", "555-1234", session)
    assert "name" in result.lower()


@pytest.mark.asyncio
async def test_update_field_rejects_placeholder():
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    session = make_mock_session()
    await executor.set_intent("routine_service", session)
    result = await executor.update_field("name", "[Name]", session)
    assert "placeholder" in result.lower() or "real" in result.lower()


# --- deliver_speak tests ---


@pytest.mark.asyncio
async def test_verbatim_speak_with_collect_lookahead():
    executor = StepExecutor(PLAYBOOK_WITH_SPEAK)
    session = make_mock_session()
    result = await executor.set_intent("test_intent", session)
    session.say.assert_not_called()
    assert 'Say EXACTLY: "Fee is $89."' in result
    assert "Confirm fee." in result
    assert executor.current_step_index == 1


@pytest.mark.asyncio
async def test_guided_speak_with_collect_lookahead():
    executor = StepExecutor(PLAYBOOK_GUIDED_SPEAK)
    session = make_mock_session()
    result = await executor.set_intent("test_intent", session)
    session.say.assert_not_called()
    assert "Greet the caller warmly." in result
    assert "Ask for name." in result
    assert executor.current_step_index == 1


# --- edge cases ---


@pytest.mark.asyncio
async def test_verbatim_speak_no_lookahead():
    """Verbatim speak with no following collect returns Say EXACTLY."""
    executor = StepExecutor(PLAYBOOK_VERBATIM_SPEAK_ALONE)
    session = make_mock_session()
    result = await executor.set_intent("test_intent", session)
    session.say.assert_not_called()
    assert 'Say EXACTLY: "Goodbye."' in result


@pytest.mark.asyncio
async def test_guided_speak_no_lookahead():
    """Guided speak without following collect returns prompt without Say EXACTLY."""
    executor = StepExecutor(PLAYBOOK_GUIDED_SPEAK_ALONE)
    session = make_mock_session()
    result = await executor.set_intent("test_intent", session)
    session.say.assert_not_called()
    assert "Let the caller know you'll take a message." in result
    assert "Say EXACTLY" not in result


@pytest.mark.asyncio
async def test_guided_speak_with_collect_no_say_exactly():
    """Guided speak with collect lookahead should NOT include Say EXACTLY."""
    executor = StepExecutor(PLAYBOOK_GUIDED_SPEAK)
    session = make_mock_session()
    result = await executor.set_intent("test_intent", session)
    assert "Say EXACTLY" not in result
    assert "Greet the caller warmly." in result
    assert "Ask for name." in result


@pytest.mark.asyncio
async def test_advance_past_end_returns_call_ended():
    """advance() past the last step returns [call_ended]."""
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    session = make_mock_session()
    await executor.set_intent("routine_service", session)
    await executor.update_field("name", "Eric", session)
    result = await executor.update_field("phone", "555-1234", session)
    assert result == "[call_ended]"


@pytest.mark.asyncio
async def test_consecutive_actions_recurse_correctly():
    """Consecutive action steps recurse through advance().
    update_field stores "yes" -> advance -> check_fee_approved (action) sees "yes" -> advance -> collect name
    """
    executor = StepExecutor(PLAYBOOK_CONSECUTIVE_ACTIONS)
    session = make_mock_session()
    await executor.set_intent("test_intent", session)
    result = await executor.update_field("fee_approved", "yes", session)
    assert result == "Ask for name."


@pytest.mark.asyncio
async def test_emergency_full_flow():
    """Emergency: collect name/phone/address -> confirm -> dispatch."""
    executor = StepExecutor(PLAYBOOK_EMERGENCY)
    session = make_mock_session()

    result = await executor.set_intent("emergency", session)
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
    executor = StepExecutor(PLAYBOOK_EMERGENCY)
    session = make_mock_session()

    await executor.set_intent("emergency", session)
    await executor.update_field("name", "Eric Tails", session)
    await executor.update_field("phone", "337-232-2341", session)
    await executor.update_field("address", "456 Cypress St 70502", session)

    result = await executor.update_field("emergency_confirmed", "no", session)
    assert "[call_ended]" in result
    assert executor.outcome == "message_taken"


@pytest.mark.asyncio
async def test_cancellation_full_flow():
    """Cancellation: collect name/phone/reason -> take_message."""
    executor = StepExecutor(PLAYBOOK_CANCELLATION)
    session = make_mock_session()

    result = await executor.set_intent("cancellation", session)
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
    executor = StepExecutor(PLAYBOOK_WARRANTY)
    session = make_mock_session()

    result = await executor.set_intent("warranty", session)
    assert 'Say EXACTLY: "All work has a one-year warranty."' in result
    assert "Ask for name." in result
    assert executor.current_step_index == 1  # Lookahead advanced past speak


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


# --- time window routing ---


@pytest.mark.asyncio
async def test_off_hours_routine_service_routes_to_after_hours():
    """Off-hours non-emergency intent is redirected to _after_hours."""
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "on_call"
    session = make_mock_session()
    result = await executor.set_intent("routine_service", session)
    assert executor.current_intent == "_after_hours"
    assert executor.requested_intent == "routine_service"
    assert "Ask for name." in result


@pytest.mark.asyncio
async def test_off_hours_emergency_keeps_full_flow():
    """Emergency intent is NOT redirected off-hours."""
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "after_hours"
    session = make_mock_session()
    await executor.set_intent("emergency", session)
    assert executor.current_intent == "emergency"
    assert executor.requested_intent is None


@pytest.mark.asyncio
async def test_off_hours_all_non_emergency_intents_reroute():
    """All non-emergency intents reroute to _after_hours off-hours, including _fallback."""
    non_emergency = ["routine_service", "cancellation", "billing", "_fallback"]
    for intent_name in non_emergency:
        executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
        executor.time_window = "on_call"
        session = make_mock_session()
        await executor.set_intent(intent_name, session)
        assert executor.current_intent == "_after_hours", (
            f"{intent_name} was not rerouted"
        )
        assert executor.requested_intent == intent_name


@pytest.mark.asyncio
async def test_office_hours_no_reroute():
    """Office hours: intents route normally, no redirect."""
    executor = StepExecutor(PLAYBOOK_WITH_AFTER_HOURS)
    executor.time_window = "office_hours"
    session = make_mock_session()
    await executor.set_intent("routine_service", session)
    assert executor.current_intent == "routine_service"
    assert executor.requested_intent is None


@pytest.mark.asyncio
async def test_off_hours_no_after_hours_intent_runs_normal_flow():
    """Off-hours with no _after_hours intent: runs normal flow, no crash."""
    executor = StepExecutor(MINIMAL_PLAYBOOK)  # has no _after_hours intent
    executor.time_window = "on_call"
    session = make_mock_session()
    await executor.set_intent("routine_service", session)
    assert executor.current_intent == "routine_service"
    assert executor.requested_intent is None


# --- field scoping tests ---


@pytest.mark.asyncio
async def test_set_intent_includes_valid_fields_for_routine():
    """set_intent result should list only routine_service fields."""
    executor = StepExecutor(MINIMAL_PLAYBOOK)
    session = make_mock_session()
    result = await executor.set_intent("routine_service", session)
    assert "Valid fields for this intent: name, phone." in result


@pytest.mark.asyncio
async def test_set_intent_includes_valid_fields_for_emergency():
    """set_intent result should list only emergency fields."""
    executor = StepExecutor(PLAYBOOK_EMERGENCY)
    session = make_mock_session()
    result = await executor.set_intent("emergency", session)
    assert "Valid fields for this intent: name, phone, address, emergency_confirmed." in result
    # Must NOT include fields from other intents
    assert "fee_approved" not in result
    assert "booking_confirmed" not in result
    assert "preferred_time" not in result
    assert "cancellation_reason" not in result


@pytest.mark.asyncio
async def test_set_intent_includes_valid_fields_for_cancellation():
    """set_intent result should list only cancellation fields."""
    executor = StepExecutor(PLAYBOOK_CANCELLATION)
    session = make_mock_session()
    result = await executor.set_intent("cancellation", session)
    assert "Valid fields for this intent: name, phone, cancellation_reason." in result
    assert "emergency_confirmed" not in result
    assert "booking_confirmed" not in result


PLAYBOOK_CROSS_INTENT = {
    "intents": {
        "routine_service": {
            "label": "Routine Service",
            "steps": [
                {"type": "collect", "field": "name", "mode": "guided", "prompt": "Ask for name."},
                {"type": "collect", "field": "phone", "mode": "guided", "prompt": "Ask for phone."},
                {"type": "collect", "field": "booking_confirmed", "mode": "guided", "prompt": "Confirm booking."},
            ],
        },
        "emergency": {
            "label": "Emergency Service",
            "steps": [
                {"type": "collect", "field": "name", "mode": "guided", "prompt": "Ask for name."},
                {"type": "collect", "field": "emergency_confirmed", "mode": "guided", "prompt": "Confirm dispatch."},
                {"type": "action", "fn": "dispatch_oncall_tech"},
            ],
        },
        "reschedule": {
            "label": "Reschedule",
            "steps": [
                {"type": "collect", "field": "name", "mode": "guided", "prompt": "Ask for name."},
                {"type": "collect", "field": "preferred_time", "mode": "guided", "prompt": "Ask when."},
                {"type": "action", "fn": "take_message"},
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            ],
        },
    },
    "service_areas": [],
    "scripts": {"closing_dispatched": "Tech sent.", "closing_message": "Message taken."},
}


@pytest.mark.asyncio
async def test_routine_service_fields_exclude_emergency_and_reschedule():
    """routine_service must not see emergency_confirmed or preferred_time."""
    executor = StepExecutor(PLAYBOOK_CROSS_INTENT)
    session = make_mock_session()
    result = await executor.set_intent("routine_service", session)
    assert "booking_confirmed" in result
    assert "emergency_confirmed" not in result
    assert "preferred_time" not in result


@pytest.mark.asyncio
async def test_emergency_fields_exclude_routine_and_reschedule():
    """emergency must not see booking_confirmed or preferred_time."""
    executor = StepExecutor(PLAYBOOK_CROSS_INTENT)
    session = make_mock_session()
    result = await executor.set_intent("emergency", session)
    assert "emergency_confirmed" in result
    assert "booking_confirmed" not in result
    assert "preferred_time" not in result


@pytest.mark.asyncio
async def test_reschedule_fields_exclude_routine_and_emergency():
    """reschedule must not see booking_confirmed or emergency_confirmed."""
    executor = StepExecutor(PLAYBOOK_CROSS_INTENT)
    session = make_mock_session()
    result = await executor.set_intent("reschedule", session)
    assert "preferred_time" in result
    assert "booking_confirmed" not in result
    assert "emergency_confirmed" not in result
