from unittest.mock import AsyncMock

import pytest

from src.actions import (
    check_emergency_confirmed,
    check_fee_approved,
    check_service_area,
    confirm_booking,
    dispatch_oncall_tech,
    take_message,
)
from src.step_executor import StepExecutor


def make_mock_session():
    session = AsyncMock()
    session.say = AsyncMock()
    return session


PLAYBOOK = {
    "meta": {"company_name": "Test Co", "timezone": "America/Chicago"},
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
            ],
        },
        "_fallback": {
            "label": "Fallback",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask name.",
                },
            ],
        },
    },
    "service_areas": ["70502", "70503"],
    "scripts": {
        "closing_booked": "All set for {appointment_time}, {name}!",
        "closing_message": "Message taken for {name}. Goodbye.",
        "closing_dispatched": "Technician dispatched. We'll call {phone}.",
    },
}


@pytest.mark.asyncio
async def test_check_fee_approved_yes():
    executor = StepExecutor(PLAYBOOK)
    executor.current_intent = "routine_service"
    # Set to -1 so advance() increments to 0 (the collect/name step).
    # This simulates the action being called mid-flow.
    executor.current_step_index = -1
    executor.collected["fee_approved"] = "yes"
    session = make_mock_session()
    result = await check_fee_approved(executor, session)
    assert result == "Ask for name."
    session.say.assert_not_called()


@pytest.mark.asyncio
async def test_check_fee_approved_no():
    executor = StepExecutor(PLAYBOOK)
    executor.collected["fee_approved"] = "no"
    session = make_mock_session()
    result = await check_fee_approved(executor, session)
    assert "[call_ended]" in result
    assert "Test Co" in result
    assert executor.outcome == "declined"
    session.say.assert_not_called()


@pytest.mark.asyncio
async def test_check_service_area_in_area():
    executor = StepExecutor(PLAYBOOK)
    executor.current_intent = "routine_service"
    # Set to -1 so advance() increments to 0 (the collect/name step)
    executor.current_step_index = -1
    executor.collected["address"] = "456 Cypress St Springfield 70502"
    session = make_mock_session()
    result = await check_service_area(executor, session)
    assert result == "Ask for name."
    session.say.assert_not_called()


@pytest.mark.asyncio
async def test_check_service_area_out_of_area():
    executor = StepExecutor(PLAYBOOK)
    executor.collected["address"] = "123 Main St Houston 77001"
    session = make_mock_session()
    result = await check_service_area(executor, session)
    assert "[call_ended]" in result
    assert "Test Co" in result
    assert executor.outcome == "out_of_area"
    session.say.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_booking_resolves_template():
    executor = StepExecutor(PLAYBOOK)
    executor.collected = {"appointment_time": "tomorrow 9am", "name": "Eric"}
    session = make_mock_session()
    result = await confirm_booking(executor, session)
    assert "[call_ended]" in result
    assert "All set for tomorrow 9am, Eric!" in result
    assert executor.outcome == "booked"
    session.say.assert_not_called()


@pytest.mark.asyncio
async def test_take_message_resolves_template():
    executor = StepExecutor(PLAYBOOK)
    executor.collected = {"name": "Eric"}
    session = make_mock_session()
    result = await take_message(executor, session)
    assert "[call_ended]" in result
    assert "Message taken for Eric. Goodbye." in result
    assert executor.outcome == "message_taken"
    session.say.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_oncall_tech_resolves_template():
    executor = StepExecutor(PLAYBOOK)
    executor.collected = {
        "phone": "337-232-2341",
        "name": "Eric",
        "address": "456 Cypress St",
    }
    session = make_mock_session()
    result = await dispatch_oncall_tech(executor, session)
    assert "[call_ended]" in result
    assert "Technician dispatched. We'll call 337-232-2341." in result
    assert executor.outcome == "dispatched"
    session.say.assert_not_called()


@pytest.mark.asyncio
async def test_check_emergency_confirmed_yes_advances():
    """When caller confirms, advance to next step (dispatch_oncall_tech)."""
    playbook = {
        "meta": {"company_name": "Test Co", "timezone": "America/Chicago"},
        "intents": {
            "emergency": {
                "label": "Emergency",
                "steps": [
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
        "scripts": {"closing_dispatched": "Tech sent to {phone}."},
    }
    executor = StepExecutor(playbook)
    executor.current_intent = "emergency"
    executor.current_step_index = 1  # on the check_emergency_confirmed action step
    executor.collected = {
        "name": "Eric",
        "phone": "337-232-2341",
        "address": "456 Cypress St",
        "emergency_confirmed": "yes",
    }
    session = make_mock_session()
    result = await check_emergency_confirmed(executor, session)
    # Should advance through dispatch_oncall_tech and return closing
    assert "[call_ended]" in result
    assert executor.outcome == "dispatched"


@pytest.mark.asyncio
async def test_check_emergency_confirmed_no_asks_what_to_change():
    """When caller says no, return guided prompt asking what to change."""
    executor = StepExecutor(PLAYBOOK)
    executor.collected = {"emergency_confirmed": "no"}
    session = make_mock_session()
    result = await check_emergency_confirmed(executor, session)
    assert "what" in result.lower() and "change" in result.lower()
