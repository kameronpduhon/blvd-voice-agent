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
    "voice": {
        "name": "Julie",
        "personality": "warm, professional, patient",
        "pace": "natural, conversational",
        "style": "friendly Southern receptionist",
    },
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


def test_missing_voice_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    del pb["voice"]
    with pytest.raises(CompilerError, match="voice"):
        validate(pb)


def test_missing_voice_name_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["voice"] = {"personality": "warm", "style": "friendly"}
    with pytest.raises(CompilerError, match="name"):
        validate(pb)


def test_first_step_action_raises():
    """Every intent's first step must be collect or speak, not action."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["intents"]["routine_service"]["steps"] = [
        {"type": "action", "fn": "take_message"},
    ]
    with pytest.raises(CompilerError, match=r"first step.*action"):
        validate(pb)


# --- compile output ---


def test_compile_produces_meta():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert result["meta"]["company_name"] == "Test Co"
    assert result["meta"]["source_file"] == "test.json"
    assert "compiled_at" in result["meta"]


def test_compile_produces_system_prompt():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert "system_prompt" in result
    prompt = result["system_prompt"]
    assert "Test Co" in prompt
    assert "set_intent" in prompt
    assert "update_field" in prompt
    assert "switch_intent" in prompt


def test_compile_no_router_or_intent_prompts():
    """Compiled output should NOT contain old multi-agent prompt keys."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert "router_prompt" not in result
    assert "intent_prompts" not in result


def test_compile_passes_through_intents():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert "routine_service" in result["intents"]
    assert "_fallback" in result["intents"]


def test_compile_passes_through_service_areas():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert result["service_areas"] == ["70502"]


# --- system prompt content ---


def test_system_prompt_includes_identity():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "Julie" in prompt
    assert "warm, professional, patient" in prompt
    assert "friendly Southern receptionist" in prompt


def test_system_prompt_includes_greeting_placeholder():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    # Greeting is now a runtime placeholder — agent.py injects the correct one
    assert "{greeting}" in prompt


def test_after_hours_greeting_not_in_prompt():
    """After-hours greeting should NOT appear in compiled prompt (injected at runtime)."""
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
    assert "Office is closed." not in prompt
    assert "{greeting}" in prompt


def test_system_prompt_includes_intent_list():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "routine_service" in prompt
    # Underscore intents should not appear in the Available intents section
    intent_start = prompt.index("Available intents:")
    intent_end = prompt.index("#", intent_start + 1)
    intent_section = prompt[intent_start:intent_end]
    bullet_lines = [line for line in intent_section.splitlines() if line.startswith("- ")]
    bullet_text = "\n".join(bullet_lines)
    assert "_fallback" not in bullet_text


def test_system_prompt_includes_emergency_qualifiers():
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
    assert "urgency" in prompt.lower()
    assert "NOT emergency" in prompt


def test_system_prompt_includes_company_info():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "Test City, TX" in prompt
    assert "(555) 555-0100" in prompt
    assert "$89" in prompt
    assert "Mike" in prompt
    assert "555-0199" in prompt


def test_system_prompt_includes_service_areas():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "70502" in prompt


def test_system_prompt_includes_tool_rules():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "NEVER" in prompt
    assert "Say EXACTLY" in prompt
    assert "[call_ended]" in prompt
    assert "zip code" in prompt.lower()
    assert "first and last name" in prompt


def test_system_prompt_includes_step_flows():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "STEP FLOW" in prompt
    assert "routine_service:" in prompt


def test_system_prompt_includes_output_rules():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "H-vac" in prompt
    assert "TTS will spell" in prompt


def test_system_prompt_includes_off_hours_section():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "OFF-HOURS" in prompt
    assert "Emergency ALWAYS" in prompt


def test_system_prompt_includes_call_closing():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "CALL CLOSING" in prompt
    assert "farewell" in prompt.lower()
    assert "DO NOT call set_intent" in prompt


def test_system_prompt_includes_info_question_handling():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["system_prompt"]
    assert "simple info" in prompt.lower() or "SIMPLE INFO" in prompt
    assert "anything else" in prompt.lower()


def test_system_prompt_valid_intent_list_for_tools():
    """Tool sections should list valid (non-underscore) intent names."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["intents"]["emergency"] = {
        "label": "Emergency Service",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
        ],
    }
    result = compile_playbook(pb, "test.json")
    prompt = result["system_prompt"]
    assert "routine_service" in prompt
    assert "emergency" in prompt


# --- after-hours validation ---


def test_after_hours_intent_and_script_both_present_passes():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["after_hours_greeting"] = "Office is closed."
    pb["intents"]["_after_hours"] = {
        "label": "After Hours Message",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
            {"type": "action", "fn": "take_message"},
        ],
    }
    validate(pb)


def test_after_hours_intent_without_script_raises():
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
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["after_hours_greeting"] = "Office is closed."
    with pytest.raises(CompilerError, match="_after_hours"):
        validate(pb)


def test_no_after_hours_support_passes():
    validate(VALID_PLAYBOOK)


# --- tts_company_name ---


def test_compile_produces_tts_company_name():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["company"]["name"] = "Cajun HVAC"
    result = compile_playbook(pb, "test.json")
    assert result["meta"]["tts_company_name"] == "Cajun H-vac"
    assert result["meta"]["company_name"] == "Cajun HVAC"


def test_compile_tts_company_name_no_hvac():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert result["meta"]["tts_company_name"] == "Test Co"


def test_collect_verbatim_rejected():
    """KAM-32: collect + mode:verbatim should be rejected by compiler."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["intents"]["routine_service"]["steps"] = [
        {"type": "collect", "field": "name", "mode": "verbatim", "text": "Some text"}
    ]
    with pytest.raises(CompilerError, match="collect steps cannot use mode 'verbatim'"):
        validate(pb)


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
