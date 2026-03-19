from unittest.mock import AsyncMock

import pytest

from src.actions import (
    check_fee_approved,
    check_service_area,
    confirm_booking,
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
    assert result == "[call_ended]"
    assert executor.outcome == "declined"
    session.say.assert_called_once()
    assert "Test Co" in session.say.call_args[0][0]


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
    assert result == "[call_ended]"
    assert executor.outcome == "out_of_area"
    session.say.assert_called_once()
    assert "Test Co" in session.say.call_args[0][0]


@pytest.mark.asyncio
async def test_confirm_booking_resolves_template():
    executor = StepExecutor(PLAYBOOK)
    executor.collected = {"appointment_time": "tomorrow 9am", "name": "Eric"}
    session = make_mock_session()
    result = await confirm_booking(executor, session)
    assert result == "[call_ended]"
    assert executor.outcome == "booked"
    session.say.assert_called_once_with("All set for tomorrow 9am, Eric!")


@pytest.mark.asyncio
async def test_take_message_resolves_template():
    executor = StepExecutor(PLAYBOOK)
    executor.collected = {"name": "Eric"}
    session = make_mock_session()
    result = await take_message(executor, session)
    assert result == "[call_ended]"
    assert executor.outcome == "message_taken"
    session.say.assert_called_once_with("Message taken for Eric. Goodbye.")
