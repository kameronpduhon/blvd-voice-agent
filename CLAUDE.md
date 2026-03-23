# CLAUDE.md

## Project Overview

Voice AI agent for home service companies (HVAC, plumbing, electrical). Handles inbound phone calls via Twilio → LiveKit SIP → Python agent. Collects caller info, routes by intent, takes action (books appointments, dispatches techs, takes messages). Each client gets a playbook (JSON config) — same codebase serves every client.

## Stack

- **Agent framework:** LiveKit Agents SDK 1.4.x (Python)
- **STT:** Deepgram Nova-3 (multilingual)
- **LLM:** OpenAI GPT-4.1-mini
- **TTS:** Deepgram Aura-2 (voice: "andromeda")
- **Package manager:** uv
- **Tests:** pytest (asyncio_mode = auto)
- **Linter:** ruff

## Commands

```bash
uv run python src/agent.py console        # Test locally in terminal
uv run python src/agent.py dev            # Connect to LiveKit Cloud
uv run python src/agent.py download-files # Download ML models (first run)
uv run pytest tests/ -v                   # Run all tests
uv run ruff check src/ compiler/ tests/   # Lint
uv run ruff format src/ compiler/ tests/  # Format
uv run python compiler/compile.py playbooks/cajun-hvac.json  # Compile playbook
```

## Architecture

**Option C: Modernized State Machine.** This is a deliberate choice — do not propose switching to LiveKit-native Agent/Task patterns.

- `StepExecutor` drives call flow via two LLM tools: `set_intent` + `update_field`
- Playbook JSON defines steps per intent (collect/speak/action)
- Compiler validates and builds system prompt — does NOT generate steps
- Per-step `mode` field: `verbatim` vs `guided` — both return text via tool result, LLM is single speech source
- Tools return `"Say EXACTLY: ..."` for verbatim text, prompts for guided
- `[call_ended]` signal in tool result = call ending, shutdown session (check with `in`, not `==`)
- `update_field` allows overwriting previously collected fields without advancing

## Project Structure

```
src/
├── agent.py           # LiveKit Agent class, entrypoint, transcript capture
├── step_executor.py   # State machine (zero LiveKit dependency)
├── actions.py         # Action functions + ACTION_REGISTRY
├── utils.py           # extract_zip, resolve_template, detect_time_window, format_hours
├── playbook.py        # Load compiled playbook from disk
└── post_call.py       # Post-call summary with retry
compiler/
└── compile.py         # Validate raw playbook → compiled JSON
playbooks/
├── cajun-hvac.json           # Raw playbook (client config)
└── cajun-hvac.compiled.json  # Compiled (agent reads this)
tests/
├── test_utils.py
├── test_step_executor.py
├── test_actions.py
└── test_compiler.py
```

## Key Rules

1. **step_executor.py has zero LiveKit SDK dependency** — pure call flow logic, independently testable
2. **No session.say() in tools** — causes double-speak. Tools return "Say EXACTLY:" directives; LLM is single speech source
3. **System prompt uses hard language** — DO NOT, NEVER (not "try to" or "please avoid")
4. **session.shutdown() is sync** — do not await it
5. **Field names must be explicit** in system prompt — LLM guesses wrong names without them
6. **conversation_item_added** is the correct event for transcript capture
7. **Running as `python src/agent.py`** requires sys.path fix for `from src.x` imports (already in agent.py and compile.py)
8. **After modifying playbook JSON**, recompile: `uv run python compiler/compile.py playbooks/cajun-hvac.json`

## Intents (10 + 1 routing)

- `routine_service` — full booking flow (fee → info → service area check → appointment → confirm → book)
- `emergency` — urgent dispatch (info → confirm → dispatch on-call tech). No fee, no service area check.
- `cancellation` — name → phone → reason → take message
- `reschedule` — name → phone → preferred time → take message
- `eta_request` — name → phone → take message
- `warranty` — speak warranty intro → name → phone → issue → take message
- `billing` — name → phone → issue → take message
- `complaint` — name → phone → issue → take message
- `commercial` — name → phone → issue → take message
- `_fallback` — name → phone → take message
- `_after_hours` — off-hours take-a-message (name → phone → take message). Only active when time_window != office_hours.

## Design Docs

- Spec (Milestone 1): `docs/superpowers/specs/2026-03-18-voice-agent-milestone1-design.md`
- Plan (Milestone 1): `docs/superpowers/plans/2026-03-18-milestone1-implementation.md`
- Spec (Intents expansion): `docs/superpowers/specs/2026-03-19-caller-intents-expansion-design.md`
- Plan (Intents expansion): `docs/superpowers/plans/2026-03-19-caller-intents-expansion.md`
- Spec (Time window routing): `docs/superpowers/specs/2026-03-23-time-window-routing-design.md`
- Plan (Time window routing): `docs/superpowers/plans/2026-03-23-time-window-routing.md`
- Prior build reference: `DUHON_VOICE_AGENT_REFERENCE.md`

## Environment Variables (.env.local)

```
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
OPENAI_API_KEY=...
DEEPGRAM_API_KEY=...
COMPILED_PLAYBOOK_PATH=playbooks/cajun-hvac.compiled.json
BACKEND_URL=http://localhost:8000
```
