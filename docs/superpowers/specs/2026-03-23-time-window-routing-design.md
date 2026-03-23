# Time Window Routing Design

## Problem

`detect_time_window()` runs at call start and stores the result (`office_hours`, `on_call`, or `after_hours`), but nothing acts on it. A caller at 9pm gets the same full booking flow as a caller at 10am. There's no calendar integration, so booking off-hours is a false promise. The agent's greeting doesn't reflect that the office is closed.

## Decision

Two modes of operation based on time window:

- **Office hours** (`office_hours`): All 10 intents work as they do today. No changes.
- **Off-hours** (`on_call` or `after_hours`): Only `emergency` gets its full flow (dispatch on-call tech). Every other intent is rerouted to `_after_hours`: collect name, collect phone, take message.

On-call exists for emergencies only. If someone calls during on-call wanting to book routine service, there's no one in the office to handle it — take a message.

## Architecture

### Enforcement: StepExecutor (deterministic)

`StepExecutor.set_intent()` checks `self.time_window` before loading steps:

```python
if self.time_window is not None and self.time_window != "office_hours" and intent != "emergency":
    self.requested_intent = intent
    intent = "_after_hours"
```

- The LLM still identifies the caller's real intent — StepExecutor handles the redirect
- `requested_intent` preserves what the caller actually wanted (for post-call summary)
- `None` time_window does NOT trigger the override (guard against uninitialized state)
- Same mechanism as routing unknown intents to `_fallback` — clean, testable

### New StepExecutor attributes

- `requested_intent: str | None` — initialized to `None` in `__init__`. Set to the caller's original intent when off-hours routing overrides it. During office hours, stays `None` (meaning `current_intent` is the requested intent).
- Post-call summary uses: `requested_intent` (what caller wanted) = `self.requested_intent or self.current_intent`, `routed_intent` (what actually ran) = `self.current_intent`.

### Tone: System prompt (conversational)

The system prompt is compiled once at build time, not at call time. Since the off-hours notice must always be present in the compiled prompt, it is phrased conditionally:

> "If the caller is reaching you outside of office hours, let them know the office is currently closed. If they describe an emergency, use set_intent('emergency'). For all other needs, use set_intent with their intent — the system will handle routing appropriately."

This way the instruction is harmless during office hours (the LLM won't mention closure if the greeting didn't) but sets the right tone when the after-hours greeting has already been spoken.

### Greeting: `on_enter()` picks the right script

`on_enter()` in `agent.py` checks `executor.time_window`:

- Office hours → `scripts.greeting` (existing)
- Off-hours → `scripts.after_hours_greeting` (new)

The caller immediately knows the office is closed and can mention if it's an emergency.

## Playbook Changes

### New script

```json
"after_hours_greeting": "Thank you for calling Cajun HVAC. Our office is currently closed. If this is an emergency such as no heat, no cooling, or a gas leak, please let me know right away. Otherwise, I can take your information and have someone call you back during business hours."
```

### New intent

```json
"_after_hours": {
  "label": "After Hours Message",
  "steps": [
    { "type": "collect", "field": "name", "mode": "guided", "prompt": "Ask for the caller's name." },
    { "type": "collect", "field": "phone", "mode": "guided", "prompt": "Ask for a callback number." },
    { "type": "action", "fn": "take_message" }
  ]
}
```

No speak step in `_after_hours` — the after-hours greeting is already spoken by `on_enter()`. Adding one here would cause double-greeting.

Note: `_after_hours` starts with `_`, so the compiler correctly excludes it from the "Available intents" list in the system prompt (same as `_fallback`). The LLM should never call `set_intent("_after_hours")` directly — StepExecutor handles the redirect.

### Compiler validation

The compiler must validate that both `_after_hours` and `_fallback` exist as required intents, and that `scripts.after_hours_greeting` is present. Without these, the agent would crash at runtime with a `KeyError` on a misconfigured playbook.

## File Changes

| File | Change |
|------|--------|
| `playbooks/cajun-hvac.json` | Add `scripts.after_hours_greeting`, add `_after_hours` intent |
| `src/agent.py` → `on_enter()` | Check `executor.time_window`, pick greeting script |
| `src/step_executor.py` → `set_intent()` | Off-hours routing override, `requested_intent` tracking |
| `compiler/compile.py` | Add off-hours notice to system prompt |
| `src/post_call.py` | Include `requested_intent` and `routed_intent` in summary |

## Testing

### New StepExecutor tests
- `test_off_hours_routine_service_routes_to_after_hours` — set `time_window = "on_call"`, call `set_intent("routine_service")`, assert `current_intent == "_after_hours"` and `requested_intent == "routine_service"`
- `test_off_hours_emergency_keeps_full_flow` — set `time_window = "after_hours"`, call `set_intent("emergency")`, assert `current_intent == "emergency"`
- `test_off_hours_all_non_emergency_intents_reroute` — loop all 9 non-emergency intents, verify each routes to `_after_hours`
- `test_office_hours_no_reroute` — set `time_window = "office_hours"`, verify intents route normally

### New compiler tests
- `test_after_hours_intent_validated` — `_after_hours` intent passes validation
- `test_system_prompt_includes_off_hours_notice` — verify off-hours section present

### Existing tests
All existing tests pass unchanged. They don't set `time_window` (defaults to `None`), and the `None` guard prevents the override from triggering.

### Not unit-tested
`on_enter()` greeting selection lives in `agent.py` which has LiveKit dependencies. Covered by console/live call testing, not unit tests.
