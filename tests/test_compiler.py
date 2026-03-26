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


def test_compile_produces_router_prompt():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["router_prompt"]
    assert "Test Co" in prompt
    assert "route_to_intent" in prompt
    assert "_fallback" in prompt
    # Router prompt should NOT contain field names or fee info
    assert "update_field" not in prompt
    assert "$89" not in prompt


def test_compile_produces_intent_prompts():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert "intent_prompts" in result
    assert "routine_service" in result["intent_prompts"]
    assert "_fallback" in result["intent_prompts"]
    # Intent prompts should contain update_field and escalate
    rs_prompt = result["intent_prompts"]["routine_service"]
    assert "update_field" in rs_prompt
    assert "escalate" in rs_prompt
    assert "NEVER" in rs_prompt
    assert "Say EXACTLY" in rs_prompt
    assert "[call_ended]" in rs_prompt


def test_compile_no_system_prompt():
    """Compiled output should NOT contain old system_prompt key."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert "system_prompt" not in result


def test_compile_passes_through_intents():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert "routine_service" in result["intents"]
    assert "_fallback" in result["intents"]


def test_compile_passes_through_service_areas():
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert result["service_areas"] == ["70502"]


def test_compile_router_prompt_includes_emergency_qualifiers():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["emergency_qualifiers"] = ["no heat", "gas leak"]
    pb["intents"]["emergency"] = {
        "label": "Emergency Service",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"}
        ],
    }
    result = compile_playbook(pb, "test.json")
    prompt = result["router_prompt"]
    assert "no heat" in prompt
    assert "gas leak" in prompt
    assert "emergency" in prompt.lower()
    # Must require urgency signals, not just symptom matching
    assert "urgency" in prompt.lower()
    # Must include contrastive examples (emergency vs NOT emergency)
    assert "NOT emergency" in prompt


def test_compile_router_prompt_without_emergency_qualifiers():
    """emergency_qualifiers is optional — playbook without it should compile fine."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert "router_prompt" in result


def test_compile_intent_prompt_includes_address_zip_instruction():
    """Intent prompts must instruct LLM to wait for complete address with zip."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["intent_prompts"]["routine_service"]
    assert "zip code" in prompt.lower()
    assert "NEVER submit a partial address" in prompt


def test_compile_intent_prompt_includes_field_names():
    """Intent prompts should list valid field names for that intent."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    rs_prompt = result["intent_prompts"]["routine_service"]
    assert "name" in rs_prompt
    assert "DO NOT invent your own field names" in rs_prompt


def test_compile_intent_prompt_scopes_company_info():
    """routine_service gets fee info; _fallback does not."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    result = compile_playbook(pb, "test.json")
    rs_prompt = result["intent_prompts"]["routine_service"]
    fb_prompt = result["intent_prompts"]["_fallback"]
    assert "$89" in rs_prompt
    assert "$89" not in fb_prompt


def test_compile_intent_prompt_name_validation():
    """Intent prompts should require first and last name."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    rs_prompt = result["intent_prompts"]["routine_service"]
    assert "first and last name" in rs_prompt


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
    # All non-underscore intents should appear in router prompt
    router_prompt = result["router_prompt"]
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
        assert intent in router_prompt
    # Each intent should have its own prompt
    assert len(result["intent_prompts"]) == 10


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


def test_router_prompt_includes_after_hours_awareness():
    """Router prompt includes after-hours awareness for the LLM."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["router_prompt"]
    assert "emergency" in prompt.lower()
    assert "route" in prompt.lower()


def test_after_hours_intent_excluded_from_router_prompt():
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
    prompt = result["router_prompt"]
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


def test_intent_prompt_has_routine_service_conversation_rules():
    """routine_service intent prompt includes specific conversation rules."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    rs_prompt = result["intent_prompts"]["routine_service"]
    assert "booking_confirmed" in rs_prompt or "appointment time" in rs_prompt


def test_intent_prompt_emergency_has_contacts():
    """Emergency intent prompt includes on-call tech contact info."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["intents"]["emergency"] = {
        "label": "Emergency Service",
        "steps": [
            {"type": "collect", "field": "name", "mode": "guided", "prompt": "Name?"},
        ],
    }
    result = compile_playbook(pb, "test.json")
    em_prompt = result["intent_prompts"]["emergency"]
    assert "Mike" in em_prompt
    assert "555-0199" in em_prompt


# --- router_acknowledgments / intent_greetings validation ---


def _pb_with_ack_and_greetings():
    """Helper: VALID_PLAYBOOK + routine_service acknowledgment + greeting."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["router_acknowledgments"] = {
        "routine_service": "Absolutely, one moment."
    }
    pb["scripts"]["intent_greetings"] = {
        "routine_service": "I'll just need a few details to get you on the schedule. What's your first and last name?"
    }
    return pb


def test_ack_and_greeting_valid_passes():
    pb = _pb_with_ack_and_greetings()
    validate(pb)  # should not raise


def test_ack_unknown_intent_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["router_acknowledgments"] = {"nonexistent": "Hello"}
    pb["scripts"]["intent_greetings"] = {"nonexistent": "Hi"}
    with pytest.raises(CompilerError, match=r"unknown intent.*nonexistent"):
        validate(pb)


def test_greeting_unknown_intent_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["router_acknowledgments"] = {"routine_service": "One moment."}
    pb["scripts"]["intent_greetings"] = {
        "routine_service": "Hi",
        "nonexistent": "Hey",
    }
    with pytest.raises(CompilerError, match=r"unknown intent.*nonexistent"):
        validate(pb)


def test_ack_without_matching_greeting_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["router_acknowledgments"] = {"routine_service": "One moment."}
    # No matching intent_greetings
    with pytest.raises(
        CompilerError, match="router_acknowledgments but no intent_greetings"
    ):
        validate(pb)


def test_greeting_without_matching_ack_raises():
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["scripts"]["intent_greetings"] = {"routine_service": "Hi there."}
    # No matching router_acknowledgments
    with pytest.raises(
        CompilerError, match="intent_greetings but no router_acknowledgments"
    ):
        validate(pb)


def test_no_ack_or_greeting_passes():
    """Playbook without router_acknowledgments or intent_greetings compiles fine."""
    validate(VALID_PLAYBOOK)  # should not raise


# --- router prompt info handling ---


def test_router_prompt_includes_company_info_for_direct_answers():
    """Router prompt should include address, phone, hours for info questions."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["router_prompt"]
    assert "Test City, TX" in prompt
    assert "(555) 555-0100" in prompt
    assert "8am" in prompt or "office hours" in prompt.lower()


def test_router_prompt_includes_info_question_instruction():
    """Router prompt should instruct LLM to answer simple info questions directly."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["router_prompt"]
    assert (
        "simple informational question" in prompt.lower()
        or "simple info" in prompt.lower()
    )
    assert "anything else" in prompt.lower()


def test_router_prompt_excludes_fees():
    """Router prompt must NOT contain fee info — that stays in intent prompts."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["router_prompt"]
    assert "$89" not in prompt
    assert "service call fee" not in prompt.lower()


# --- intent prompt greeting instruction ---


def test_intent_prompt_greeting_instruction_for_greeted_intent():
    """Intent prompt for greeted intent should include 'do not re-ask' instruction."""
    pb = _pb_with_ack_and_greetings()
    result = compile_playbook(pb, "test.json")
    rs_prompt = result["intent_prompts"]["routine_service"]
    assert "greeting" in rs_prompt.lower()
    assert "do not re-ask" in rs_prompt.lower()


def test_intent_prompt_no_greeting_instruction_for_ungreeted_intent():
    """Intent prompt for non-greeted intent should NOT have greeting instruction."""
    pb = _pb_with_ack_and_greetings()
    result = compile_playbook(pb, "test.json")
    fb_prompt = result["intent_prompts"]["_fallback"]
    assert "already been asked" not in fb_prompt.lower()


def test_intent_prompt_no_greeting_block_for_ungreeted_intent():
    """Non-greeted intent prompt should have explicit no-greeting handoff block."""
    pb = _pb_with_ack_and_greetings()
    result = compile_playbook(pb, "test.json")
    fb_prompt = result["intent_prompts"]["_fallback"]
    assert "DO NOT greet the caller" in fb_prompt
    assert "DO NOT say" in fb_prompt
    assert "introduce yourself" in fb_prompt


def test_compiled_output_includes_router_acknowledgments_in_scripts():
    """Compiled output scripts should include router_acknowledgments."""
    pb = _pb_with_ack_and_greetings()
    result = compile_playbook(pb, "test.json")
    assert "router_acknowledgments" in result["scripts"]
    assert "routine_service" in result["scripts"]["router_acknowledgments"]


def test_compiled_output_includes_intent_greetings_in_scripts():
    """Compiled output scripts should include intent_greetings."""
    pb = _pb_with_ack_and_greetings()
    result = compile_playbook(pb, "test.json")
    assert "intent_greetings" in result["scripts"]
    assert "routine_service" in result["scripts"]["intent_greetings"]


# --- tts_company_name ---


def test_compile_produces_tts_company_name():
    """Compiled meta includes tts_company_name with HVAC replaced."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["company"]["name"] = "Acme HVAC"
    result = compile_playbook(pb, "test.json")
    assert result["meta"]["tts_company_name"] == "Acme H-vac"
    assert result["meta"]["company_name"] == "Acme HVAC"


def test_compile_tts_company_name_no_hvac():
    """Company name without HVAC gets tts_company_name unchanged."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    assert result["meta"]["tts_company_name"] == "Test Co"


def test_compile_output_rule_hvac():
    """Output rules should instruct LLM to write H-vac, not HVAC."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["intent_prompts"]["routine_service"]
    assert "H-vac" in prompt
    assert 'all capital letters' in prompt.lower() or 'TTS will spell' in prompt


def test_compile_router_prompt_no_speak_after_routing():
    """Router prompt should instruct LLM not to speak after calling route_to_intent."""
    result = compile_playbook(VALID_PLAYBOOK, "test.json")
    prompt = result["router_prompt"]
    assert "DO NOT speak" in prompt or "Do NOT speak" in prompt
    assert "transferring" in prompt.lower() or "please hold" in prompt.lower()


def test_compile_appointment_time_instruction():
    """Intent prompts should include instruction about collecting complete appointment times."""
    pb = json.loads(json.dumps(VALID_PLAYBOOK))
    pb["intents"]["routine_service"]["steps"].append(
        {"type": "collect", "field": "appointment_time", "mode": "guided", "prompt": "When?"}
    )
    result = compile_playbook(pb, "test.json")
    prompt = result["intent_prompts"]["routine_service"]
    assert "appointment time" in prompt.lower()
    assert "day AND" in prompt or "day and" in prompt.lower()
