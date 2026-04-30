# Prior Build — Architecture Reference

This document describes a previous working voice agent build (a Laravel-API-backed Python LiveKit agent). Kept here as context for the architectural decisions that informed the current codebase.

---

## What It Does

AI voice agent that answers inbound phone calls for home service companies (HVAC, plumbing, electrical). It collects caller information, routes the call by intent, and takes action (books appointments, dispatches techs, takes messages).

Each client gets a **playbook** — a JSON config file that defines their company info, hours, fees, scripts, contacts, and intent configurations. The agent is fully parameterized by this playbook. Same codebase serves every client.

---

## System Overview

```
Twilio (phone number)
    → LiveKit SIP Trunk
        → Python Voice Agent (agent.py)
            ↔ LLM (GPT-4.1-mini) via tool calls
            → Laravel API (config + post-call data)
```

---

## Stack

| Layer | Tech |
|-------|------|
| Phone provider | Twilio |
| Media server | LiveKit (SIP trunk) |
| Agent framework | LiveKit Agents SDK 1.4.4 |
| STT | Deepgram Nova-3 (streaming) |
| LLM | GPT-4.1-mini (text + tool calling) |
| TTS | Deepgram Aura-2 (aura-2-andromeda-en) |
| Backend API | Laravel (PHP) |
| Playbook format | JSON on disk |

**Python version:** 3.12 (required for livekit-agents)

---

## Directory Structure

```
voice-agent/
├── agent/
│   ├── agent.py              # Main voice agent
│   ├── venv/                  # Python 3.12 virtual environment
│   └── .env                   # Agent env vars
├── compiler/
│   └── compile.py             # Playbook compiler
├── playbooks/
│   ├── acme-hvac.json        # Raw playbook (client config)
│   └── acme-hvac.compiled.json  # Compiled output (agent reads this)
├── tests/
│   ├── test_unit.py           # 81 unit tests
│   └── scripts/               # Manual call test scripts (01-05)
├── app/                       # Laravel backend
├── routes/
│   └── api.php                # API routes
└── ...                        # Standard Laravel structure
```

---

## Three Layers

### Layer 1: Playbook JSON (Client Config)

**File:** `playbooks/{client}.json`

The playbook is what a client fills out. It contains everything the agent needs to handle their calls:

- **Company info** — name, address, phone
- **Service areas** — list of zip codes they serve
- **Hours** — office hours, on-call hours, cutoff times
- **Fees** — service call fees, after-hours fees, waiver rules
- **Contacts** — on-call tech info, office contacts
- **Scripts** — greeting, closing (booked/dispatched/message), custom lines
- **Intent configs** — which intents are enabled, emergency qualifiers, cancellation reason toggle

### Layer 2: Compiler

**File:** `compiler/compile.py`
**Run:** `python compiler/compile.py playbooks/{client}.json`

Takes raw playbook JSON → outputs compiled JSON. The compiled output is what the agent actually loads at runtime.

**Compiled output structure:**
```json
{
  "meta": {
    "company_name": "Acme HVAC",
    "timezone": "America/Chicago",
    "compiled_at": "...",
    "source_file": "acme-hvac.json"
  },
  "global": {
    "system_prompt": "You are a virtual receptionist for Acme HVAC...",
    "company_info": {},
    "service_areas": ["12345", "12346"],
    "hours": {
      "office_hours": { "start": "08:00", "end": "17:00", "days": ["mon","tue","wed","thu","fri"] },
      "on_call": { "start": "17:00", "end": "22:00" },
      "cutoffs": {}
    },
    "fees": [
      { "name": "service_call_fee", "amount": 89, "waived_with_work": true, "collection_prompt": "..." }
    ],
    "contacts": {
      "oncall_tech": { "name": "...", "phone": "..." },
      "all": [...]
    },
    "scripts": {
      "greeting": "Thank you for calling Acme HVAC...",
      "closing_booked": "...",
      "closing_dispatched": "...",
      "closing_message": "..."
    }
  },
  "intents": {
    "routine_service": {
      "label": "Routine Service Request",
      "steps": [...]
    },
    "emergency": {
      "label": "Emergency Service",
      "emergency_qualifiers": ["no heat", "gas leak", ...],
      "steps": [...]
    }
  }
}
```

### Layer 3: Voice Agent

**File:** `agent/agent.py`
**Start:** `cd agent && source venv/bin/activate && python agent.py dev`

The agent loads a compiled playbook and drives calls using a state machine.

---

## State Machine (StepExecutor)

The `StepExecutor` class is the core of the agent. It tracks:

- `current_intent` — which intent the call was routed to (set once)
- `current_step_index` — which step we're on in that intent's step array
- `collected` — dict of all field values gathered from the caller
- `transcript` — running transcript of the call
- `outcome` — final result (booked / dispatched / message_taken)

### Step Types (3 total)

| Type | Purpose | Key Fields |
|------|---------|------------|
| `collect` | Ask the caller for one piece of info | `field`, `prompt` |
| `speak` | Say something (no response expected) | `text` |
| `action` | Run a Python function (no LLM involved) | `fn`, optional `on_fail`, `params` |

### Intent Step Sequences

These are currently **hardcoded in the compiler** (not in the playbook JSON):

- **routine_service:** fee_approved → name → phone → address → check_service_area → appointment_time → confirm_booking
- **emergency:** fee_approved → name → phone → address → summary_confirmed → dispatch_oncall_tech
- **cancellation:** name → phone → [cancellation_reason] → take_message
- **reschedule:** name → phone → preferred_time → take_message
- **eta_request:** name → phone → take_message
- **warranty:** speak(script) → name → phone → issue_description → take_message
- **billing:** name → phone → issue_description → take_message
- **complaint:** name → phone → complaint_description → take_message
- **commercial:** name → phone → issue_description → take_message
- **out_of_area:** speak(full goodbye)

---

## LLM Interface — Two Tools Only

The entire interface between the LLM and the state machine is two tools:

### `set_intent(intent: str)`
- Called **once** after the greeting, when the LLM identifies what the caller needs
- Routes the call to the matching intent's step array
- Returns a speech instruction (the first step's prompt)

### `update_field(field_name: str, value: str)`
- Called each time the caller provides a piece of info
- Records the value in `collected`, advances `current_step_index`
- Returns the next step's speech instruction
- If the next step is an `action`, the Python function executes immediately and returns the action's result (closing script, etc.)

**Key principle:** Tools return speech instructions as strings. The LLM speaks them. The LLM never generates its own dialogue for collecting fields — it follows what the state machine tells it to say.

---

## Action Functions

These run inside the agent when an `action` step is reached:

| Function | What It Does |
|----------|-------------|
| `check_service_area` | Extracts zip from collected address, checks against `service_areas` list. If out of area → routes to `out_of_area` intent. |
| `confirm_booking` | Resolves closing script, sets outcome to `booked`, fires `post_summary()` |
| `dispatch_oncall_tech` | Resolves closing script, sets outcome to `dispatched`, fires `post_dispatch()` |
| `take_message` | Resolves closing script, sets outcome to `message_taken` |

---

## Call Flow (step by step)

1. Call comes in via Twilio → LiveKit SIP trunk → agent connects
2. Agent loads compiled playbook from `COMPILED_PLAYBOOK_PATH`
3. `detect_time_window()` determines: office_hours / on_call / after_hours
4. System prompt is built from compiled `global` section
5. Agent session starts with LLM + tools registered
6. `generate_reply(greeting_script)` — sends the greeting (this is the **only** `generate_reply` call)
7. Caller speaks → LLM identifies intent → calls `set_intent(intent)` → returns first step prompt
8. LLM speaks the prompt → caller answers → LLM calls `update_field(field, value)` → next step
9. Repeat step 8 until an `action` step is reached
10. Action function runs → returns closing speech → LLM says it
11. Caller hangs up → `participant_disconnected` → `post_summary()` fires

---

## Critical Design Rules

These were learned from testing. Violating any of them causes bugs:

1. **Tools return speech, never `generate_reply`** — if both fire, you get double-speak (agent says the same thing twice or says two conflicting things).

2. **Speak step lookahead** — if a `speak` step is followed by a `collect` step, combine them into one instruction. Otherwise there's an awkward silence between the speak and the question.

3. **System prompt must use hard language** — "DO NOT" and "NEVER", not "try to" or "please avoid". The LLM follows hard rules reliably; soft rules get ignored.

4. **No placeholder values** — system prompt explicitly forbids calling `update_field` with values like `[Name]`, `[Address]`, `TBD`. Only real caller-provided values.

5. **`set_intent` is called once** — system prompt says "NEVER call set_intent again" to prevent re-routing mid-call.

6. **Declined appointment slots** — when caller declines a suggested time, agent asks what works for them, then calls `update_field('appointment_time', new_value)`. Handled via system prompt instruction, not a separate step.

---

## Backend API (Laravel)

### Endpoints the agent calls:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/agent/playbook?dnis={dnis}` | Fetch compiled playbook by phone number (future — currently reads from disk) |
| POST | `/api/call/summary` | Post call summary after call ends |

### Summary payload structure:
```json
{
  "dnis": "5551002000",
  "caller_number": "3372322341",
  "intent": "routine_service",
  "outcome": "booked",
  "collected": {
    "name": "Eric Tails",
    "phone": "3372322341",
    "address": "456 Cypress St Springfield 12345",
    "appointment_time": "Tomorrow at 9am"
  },
  "transcript": "...",
  "duration_seconds": 142,
  "time_window": "office_hours"
}
```

---

## Environment Variables

```env
# agent/.env
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
OPENAI_API_KEY=...
DEEPGRAM_API_KEY=...
COMPILED_PLAYBOOK_PATH=../playbooks/acme-hvac.compiled.json
BACKEND_URL=http://localhost:8000
DEFAULT_DNIS=unknown
```

---

## Testing

- **Unit tests:** `tests/test_unit.py` — 81 tests, ~0.55s, no LLM/network calls
- **Manual call scripts:** `tests/scripts/` — 5 scripts covering all major call flows
- **Run:** `source agent/venv/bin/activate && pytest tests/ -v`

**Test caller info:**
- Name: Eric Tails
- Phone: (337) 232-2341
- In-area address: 456 Cypress St Springfield 12345
- Out-of-area zip: 70501

---

## Twilio / LiveKit Config

- **Twilio number:** (555) 100-2000
- **LiveKit SIP trunk:** `ST_A6GagnMmUDqo`

---

## Known Limitations

1. **Step order is hardcoded in the compiler** — the compiler generates step arrays in Python code. Clients can't reorder steps via the playbook JSON. Future: define step arrays directly in the playbook.

2. **Playbook loaded from disk** — agent reads `COMPILED_PLAYBOOK_PATH` on startup. For multi-client, needs to fetch via API using DNIS (phone number routing).

3. **No hot-reload** — changing a playbook requires restarting the agent.

4. **Realtime API branch untested** — `feature/realtime-api` (commit `c6a81ca`) replaces the STT/LLM/TTS pipeline with OpenAI Realtime API. Built but never live-tested.

---

## What This Agent Does NOT Handle (out of scope for the voice agent itself)

- Playbook creation/editing (handled by a separate Laravel back-office app)
- User auth / client dashboard (handled by the same back-office app)
- Call recording storage (handled by Twilio + S3 in the platform layer)
- CRM integration (future — ServiceTitan API)
