# Cajun HVAC Voice Agent

Voice AI agent for home service companies (HVAC, plumbing, electrical). Handles inbound phone calls end-to-end: collects caller info, routes by intent, and takes action — books appointments, dispatches on-call techs, or takes messages.

Built on **Twilio SIP + LiveKit Agents SDK** with a playbook-driven architecture. Each client gets a JSON playbook config; the same codebase serves every client.

## Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LiveKit Agents SDK 1.4.x (Python) |
| Speech-to-text | Deepgram Nova-3 (multilingual) |
| LLM | OpenAI GPT-4.1-mini |
| Text-to-speech | Deepgram Aura-2 |
| Telephony | Twilio → LiveKit SIP |
| Package manager | uv |

## How It Works

A **modernized state machine** drives every call:

1. Caller dials in via Twilio, which connects to a LiveKit SIP room
2. The Python agent joins the room and greets the caller
3. `StepExecutor` walks through playbook-defined steps using two LLM tools: `set_intent` and `update_field`
4. Steps collect fields, speak scripts, or fire actions (book appointment, dispatch tech, take message)
5. Post-call summary is sent to the backend

The playbook compiler validates client config and builds the system prompt — the agent reads only the compiled output.

## Supported Intents

| Intent | Flow |
|--------|------|
| `routine_service` | Fee disclosure → info collection → service area check → appointment → confirm → book |
| `emergency` | Info collection → confirm → dispatch on-call tech |
| `cancellation` | Name → phone → reason → take message |
| `reschedule` | Name → phone → preferred time → take message |
| `eta_request` | Name → phone → take message |
| `warranty` | Warranty intro → name → phone → issue → take message |
| `billing` | Name → phone → issue → take message |
| `complaint` | Name → phone → issue → take message |
| `commercial` | Name → phone → issue → take message |
| `_fallback` | Name → phone → take message |

## Project Structure

```
src/
├── agent.py           # LiveKit Agent, entrypoint, transcript capture
├── step_executor.py   # State machine (zero LiveKit dependency)
├── actions.py         # Action functions + ACTION_REGISTRY
├── utils.py           # Helpers: templates, time windows, formatting
├── playbook.py        # Load compiled playbook from disk
└── post_call.py       # Post-call summary with retry
compiler/
└── compile.py         # Validate raw playbook → compiled JSON
playbooks/
├── cajun-hvac.json           # Raw playbook (client config)
└── cajun-hvac.compiled.json  # Compiled output (agent reads this)
tests/
├── test_utils.py
├── test_step_executor.py
├── test_actions.py
└── test_compiler.py
```

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

```bash
# Install dependencies
uv sync

# Copy env template and fill in your keys
cp .env.local.example .env.local

# Download ML models (first run only)
uv run python src/agent.py download-files

# Compile the playbook
uv run python compiler/compile.py playbooks/cajun-hvac.json
```

### Environment Variables

Create a `.env.local` file with:

```
LIVEKIT_URL=wss://your-livekit-instance.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
OPENAI_API_KEY=...
DEEPGRAM_API_KEY=...
COMPILED_PLAYBOOK_PATH=playbooks/cajun-hvac.compiled.json
BACKEND_URL=http://localhost:8000
```

### Run

```bash
# Test locally in terminal
uv run python src/agent.py console

# Connect to LiveKit Cloud
uv run python src/agent.py dev
```

### Test & Lint

```bash
uv run pytest tests/ -v
uv run ruff check src/ compiler/ tests/
uv run ruff format src/ compiler/ tests/
```

## Playbook System

Each client is configured via a JSON playbook that defines:

- **Company info** — name, phone, hours, service areas, fees
- **Intents** — what the caller might need
- **Steps per intent** — ordered sequence of collect, speak, and action steps
- **Modes** — `verbatim` (exact script) or `guided` (LLM has flexibility)

To modify a playbook, edit the raw JSON then recompile:

```bash
uv run python compiler/compile.py playbooks/cajun-hvac.json
```

## License

Private — all rights reserved.
