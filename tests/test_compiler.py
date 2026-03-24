import json

import pytest

from compiler.compile import CompilerError, compile_playbook, validate

VALID_PLAYBOOK = {
    "company": {
        "name": "Test Co",
        "phone": "(555) 555-0100",
        "address": "Test City, TX",
        "timezone": "America/Chicago",
    },
    "hours": {
        "office": {
            "start": "08:00",
            "end": "17:00",
            "days": ["mon", "tue", "wed", "thu", "fri"],
        },
        "on_call": {"start": "17:00", "end": "22:00"},
    },
    "service_areas": ["70502"],
    "fees": {"service_call": {"amount": 89, "waived_with_work": True}},
    "contacts": {"oncall_tech": {"name": "Mike", "phone": "(555) 555-0199"}},
    "scripts": {
        "greeting": "Hello!",
        "closing_booked": "Booked for {appointment_time}.",
        "closing_message": "Message taken.",
    },
    "intents": {
        "routine_service": {
            "label": "Routine Service",
            "steps": [
                {
                    "type": "collect",
                    "field": "name",
                    "mode": "guided",
                    "prompt": "Ask name.",
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
}


def test_valid_playbook_passes():
    validate(VALID_PLAYBOOK)


def test_missing_company_raises():
    pb = {**VALID_PLAYBOOK}
    del pb["company"]
    with pytest.raises(CompilerError, match="company"):
        validate(pb)


def test_missing_fallback_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    del pb["intents"]["_fallback"]
    with pytest.raises(CompilerError, match="_fallback"):
        validate(pb)


def test_missing_mode_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["intents"]["routine_service"]["steps"] = [
        {"type": "collect", "field": "name", "prompt": "Ask name."},
    ]
    with pytest.raises(CompilerError, match="mode"):
        validate(pb)


def test_speak_verbatim_missing_text_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["intents"]["routine_service"]["steps"] = [
        {"type": "speak", "mode": "verbatim", "prompt": "Wrong field."},
    ]
    with pytest.raises(CompilerError, match="text"):
        validate(pb)


def test_unknown_action_fn_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["intents"]["routine_service"]["steps"] = [
        {"type": "action", "fn": "nonexistent_function"},
    ]
    with pytest.raises(CompilerError, match="nonexistent_function"):
        validate(pb)


def test_compile_produces_meta():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert result["meta"]["company_name"] == "Test Co"
    assert result["meta"]["source_file"] == "test.json"
    assert "compiled_at" in result["meta"]


def test_compile_produces_system_prompt():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "Test Co" in prompt
    assert "set_intent" in prompt
    assert "update_field" in prompt
    assert "NEVER" in prompt
    assert "Say EXACTLY" in prompt
    assert "[call_ended]" in prompt
    assert "_fallback" in prompt


def test_compile_passes_through_intents():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert "routine_service" in result["intents"]
    assert "_fallback" in result["intents"]


def test_compile_passes_through_service_areas():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert result["service_areas"] == ["70502"]


def test_compile_system_prompt_includes_emergency_qualifiers():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["emergency_qualifiers"] = ["no heat", "gas leak"]
    pb["intents"]["emergency"] = {
        "label": "Emergency Service",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"}
        ],
    }
    result = compile_playbook(pb, "test.json")
    prompt = result["system_prompt"]
    assert "no heat" in prompt
    assert "gas leak" in prompt
    assert "emergency" in prompt.lower()
    # Must require urgency signals, not just symptom matching
    assert "urgency" in prompt.lower()
    # Must include contrastive examples (emergency vs NOT emergency)
    assert "NOT emergency" in prompt


def test_compile_system_prompt_without_emergency_qualifiers():
    """emergency_qualifiers is optional — playbook without it should compile fine."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    # Should not crash, just no qualifiers section
    assert "system_prompt" in result


def test_compile_system_prompt_no_global_field_list():
    """System prompt should NOT contain a global field name list (fields are scoped per-intent at runtime)."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "The field names are:" not in prompt
    # Should instruct to use only fields from set_intent response
    assert "set_intent response" in prompt or "set_intent" in prompt
    assert "DO NOT invent your own field names" in prompt


def test_compile_all_ten_intents():
    """Full playbook with all 10 intents compiles without error."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["closing_dispatched"] = "Tech sent to {phone}."
    pb["emergency_qualifiers"] = ["no heat", "gas leak"]
    pb["intents"]["emergency"] = {
        "label": "Emergency Service",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "check_emergency_confirmed"},
            {"type": "action", "fn": "dispatch_oncall_tech"},
        ],
    }
    pb["intents"]["cancellation"] = {
        "label": "Cancel Appointment",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    pb["intents"]["reschedule"] = {
        "label": "Reschedule Appointment",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    pb["intents"]["eta_request"] = {
        "label": "Technician ETA Request",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    pb["intents"]["warranty"] = {
        "label": "Warranty Claim",
        "steps": [
            {"type": "speak", "mode": "verbatim", "text": "Warranty info."},
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    pb["intents"]["billing"] = {
        "label": "Billing Question",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    pb["intents"]["complaint"] = {
        "label": "Customer Complaint",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    pb["intents"]["commercial"] = {
        "label": "Commercial Service Request",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    result = compile_playbook(pb, "test.json")
    assert len(result["intents"]) == 10
    prompt = result["system_prompt"]
    # All non-underscore intents should appear in Available intents
    for intent in [
        "routine_service",
        "emergency",
        "cancellation",
        "reschedule",
        "eta_request",
        "warranty",
        "billing",
        "complaint",
        "commercial",
    ]:
        assert intent in prompt


def test_after_hours_intent_and_script_both_present_passes():
    """Playbook with both _after_hours intent and after_hours_greeting compiles fine."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["after_hours_greeting"] = "Office is closed."
    pb["intents"]["_after_hours"] = {
        "label": "After Hours Message",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    validate(pb)  # should not raise


def test_after_hours_intent_without_script_raises():
    """_after_hours intent without after_hours_greeting script is a compiler error."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["intents"]["_after_hours"] = {
        "label": "After Hours Message",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    with pytest.raises(CompilerError, match="after_hours_greeting"):
        validate(pb)


def test_after_hours_script_without_intent_raises():
    """after_hours_greeting script without _after_hours intent is a compiler error."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["after_hours_greeting"] = "Office is closed."
    with pytest.raises(CompilerError, match="_after_hours"):
        validate(pb)


def test_no_after_hours_support_passes():
    """Playbook without _after_hours or after_hours_greeting compiles fine."""
    validate(VALID_PLAYBOOK)  # should not raise — already works, but making it explicit


def test_system_prompt_includes_off_hours_notice():
    """System prompt includes conditional off-hours guidance for the LLM."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "outside of office hours" in prompt


def test_after_hours_intent_excluded_from_available_intents():
    """_after_hours (underscore prefix) must NOT appear in Available intents list."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["after_hours_greeting"] = "Office is closed."
    pb["intents"]["_after_hours"] = {
        "label": "After Hours Message",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    result = compile_playbook(pb, "test.json")
    prompt = result["system_prompt"]
    # Extract only the bullet-point lines in the Available intents section
    intents_start = prompt.index("# Available intents")
    intents_end = prompt.index("#", intents_start + 1)
    intents_section = prompt[intents_start:intents_end]
    # Only the bullet lines list intents — underscore intents must not appear there
    bullet_lines = [
        line for line in intents_section.splitlines() if line.startswith("- ")
    ]
    bullet_text = "\n".join(bullet_lines)
    assert "_after_hours" not in bullet_text
    assert "_fallback" not in bullet_text  # confirm existing behavior too
