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
    assert result == "Ask for name."
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
    session.say.assert_called_once_with("Fee is $89.")
    assert result == "Confirm fee."
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
async def test_verbatim_speak_no_lookahead_returns_delivered():
    """Verbatim speak with no following collect returns [delivered]."""
    executor = StepExecutor(PLAYBOOK_VERBATIM_SPEAK_ALONE)
    session = make_mock_session()
    result = await executor.set_intent("test_intent", session)
    session.say.assert_called_once_with("Goodbye.")
    assert result == "[delivered]"


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
