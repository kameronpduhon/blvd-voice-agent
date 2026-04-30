# BLVD Voice Agent

Voice AI agent for home service companies (HVAC, plumbing, electrical). Handles inbound phone calls end-to-end: greets the caller, routes by intent, collects the right fields for that intent, and fires an action — book an appointment, dispatch the on-call tech, or take a message. Each client gets a JSON playbook config; the same codebase serves every client.

I built this as the second iteration of a voice-agent platform after a Laravel-backed first version. The split here is deliberate: a `RouterAgent` handles intent identification and simple info questions, then hands off to a parameterized `IntentAgent` that runs that intent's flow. The LiveKit-free `StepExecutor` underneath drives the call flow as a pure-Python state machine, so the call logic is testable end-to-end without spinning up a SIP room.

## Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LiveKit Agents SDK 1.4.x (Python) |
| Speech-to-text | Deepgram Nova-3 (multilingual, streaming) |
| LLM | OpenAI GPT-4.1-mini |
| Text-to-speech | Deepgram Aura-2 |
| Telephony | Twilio → LiveKit SIP |
| Package manager | uv |
| Tests | pytest (asyncio_mode=auto) |
| Lint / format | ruff |

## How It Works

A two-agent handoff drives every call:

1. Caller dials a Twilio number, which routes to a LiveKit SIP room.
2. `RouterAgent` greets the caller, identifies intent (`route_to_intent` tool), checks the time window, speaks a short acknowledgment, and hands off to an `IntentAgent`.
3. `IntentAgent` runs the intent's flow using `update_field` and `escalate` tools. The underlying `StepExecutor` walks through playbook-defined steps (collect / speak / action).
4. Steps either collect a field, speak a script (verbatim or LLM-paraphrased), or fire an action (`check_service_area`, `dispatch_oncall_tech`, `take_message`, etc.).
5. Post-call summary is sent to the configured backend.

Single-voice UX is the goal: the caller should never feel like they were transferred. Router acknowledgments and intent continuation phrases are paired so the handoff sounds like the same agent shifting gears. The compiler validates that pairing.

## Supported Intents

| Intent | Flow |
|--------|------|
| `routine_service` | Name → phone → address → area check → appointment → issue → fee disclosure → confirm → book |
| `emergency` | Name → phone → address → confirm → dispatch on-call tech (no fee, no service-area check) |
| `cancellation` | Name → phone → reason → take message |
| `reschedule` | Name → phone → preferred time → take message |
| `eta_request` | Name → phone → take message |
| `warranty` | Warranty intro → name → phone → issue → take message |
| `billing` | Name → phone → issue → take message |
| `complaint` | Name → phone → issue → take message |
| `commercial` | Name → phone → issue → take message |
| `_fallback` | Name → phone → take message |
| `_after_hours` | Name → phone → take message (only active outside office hours) |

## Project Structure

```
src/
├── agent.py           # RouterAgent + IntentAgent, entrypoint, transcript capture
├── step_executor.py   # State machine (zero LiveKit dependency, fully unit-tested)
├── actions.py         # Action functions + ACTION_REGISTRY
├── utils.py           # Helpers: time windows, templates, formatting
├── playbook.py        # Load compiled playbook from disk
└── post_call.py       # Post-call summary with retry
compiler/
└── compile.py         # Validate raw playbook → compiled JSON (router_prompt + intent_prompts)
playbooks/
├── acme-hvac.json           # Sample raw playbook
└── acme-hvac.compiled.json  # Compiled output (agent reads this)
tests/
├── test_utils.py
├── test_step_executor.py
├── test_actions.py
└── test_compiler.py
docs/

PRIOR_BUILD_REFERENCE.md     # Architecture notes from the v1 (Laravel-backed) build
```

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- LiveKit Cloud project (or self-hosted LiveKit server)
- Twilio account with a SIP-enabled phone number
- Deepgram and OpenAI API keys

### Setup

```bash
uv sync
cp .env.example .env.local
# Fill in keys in .env.local

uv run python src/agent.py download-files
uv run python compiler/compile.py playbooks/acme-hvac.json
```

### Environment Variables

```
LIVEKIT_URL=wss://your-instance.livekit.cloud
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
OPENAI_API_KEY=
DEEPGRAM_API_KEY=
COMPILED_PLAYBOOK_PATH=playbooks/acme-hvac.compiled.json
BACKEND_URL=http://localhost:8000
```

### Run

```bash
uv run python src/agent.py console   # Test locally in the terminal
uv run python src/agent.py dev       # Connect to LiveKit Cloud
```

### Test and lint

```bash
uv run pytest tests/ -v
uv run ruff check src/ compiler/ tests/
uv run ruff format src/ compiler/ tests/
```

## Playbook System

Each client is configured via a JSON playbook that defines:

- **Company info** — name, phone, hours, service areas, fees
- **Voice** — name, personality, pace, style for the receptionist persona
- **Scripts** — greeting, closings, after-hours message
- **Intents** — what the caller might need
- **Steps per intent** — ordered sequence of `collect`, `speak`, and `action` steps
- **Modes** — `verbatim` (exact script) or `guided` (LLM paraphrases)

The compiler validates the raw playbook, builds the router prompt and per-intent prompts, and writes a compiled JSON file. The agent reads only the compiled output. To modify a playbook, edit the raw JSON then recompile:

```bash
uv run python compiler/compile.py playbooks/acme-hvac.json
```

The bundled `playbooks/acme-hvac.json` is a sample HVAC config with placeholder phone numbers and zip codes. Use it as a starting point for a real client config.

## Architecture Notes

- `step_executor.py` has zero LiveKit dependency. The state machine is pure Python and can be unit-tested without a SIP room or any audio infrastructure.
- Tools never call `session.say()` — that causes double-speak. Instead, tools return `"Say EXACTLY: ..."` directives and the LLM is the single speech source. The one exception is `route_to_intent`, which uses `session.say(allow_interruptions=False)` to play the router acknowledgment before handing off (so the caller hears it through the handoff).
- Intent prompts use hard language (`DO NOT`, `NEVER`) rather than soft hedging — the agent is more reliable when constraints are framed unambiguously.
- Field names are auto-generated by the compiler from `collect` steps. There's no hardcoded field list to keep in sync.
- Transcript capture lives on `session.userdata` rather than the agent instance — agent instances change on handoff, but the session persists.

## License

MIT
