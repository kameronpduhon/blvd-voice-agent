import logging
import re

from src.actions import ACTION_REGISTRY

logger = logging.getLogger("agent")

DAY_ONLY_PATTERN = re.compile(
    r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"mon|tue|wed|thu|fri|sat|sun|"
    r"today|tomorrow|next week)$",
    re.IGNORECASE,
)


def _is_incomplete_appointment_time(value: str) -> bool:
    """Check if appointment time is just a day without a specific time."""
    return bool(DAY_ONLY_PATTERN.match(value.strip()))


PLACEHOLDER_PATTERNS = {
    "[name]",
    "[address]",
    "[phone]",
    "tbd",
    "n/a",
    "unknown",
    "[value]",
}


class StepExecutor:
    def __init__(self, playbook: dict):
        self.playbook = playbook
        self.current_intent: str | None = None
        self.current_step_index: int = 0
        self.collected: dict[str, str] = {}
        self.transcript: str = ""
        self.outcome: str | None = None
        self.time_window: str | None = None
        self.call_start_time: float | None = None
        self.requested_intent: str | None = None

    def _skip_pre_collected_steps(self):
        """Skip past collect steps for fields that are already in self.collected."""
        while self.current_step_index < len(self.current_steps):
            step = self.current_steps[self.current_step_index]
            if step["type"] == "collect" and step["field"] in self.collected:
                self.current_step_index += 1
            else:
                break

    @property
    def company_tts_name(self) -> str:
        meta = self.playbook.get("meta", {})
        return meta.get("tts_company_name", meta.get("company_name", "us"))

    @property
    def current_steps(self) -> list[dict]:
        if self.current_intent is None:
            return []
        return self.playbook["intents"][self.current_intent]["steps"]

    def peek_next_step(self) -> dict | None:
        next_idx = self.current_step_index + 1
        if next_idx < len(self.current_steps):
            return self.current_steps[next_idx]
        return None

    def set_intent(self, intent: str, session) -> str:
        """Called once after greeting when LLM identifies caller's need.
        Handles off-hours routing internally."""

        # Validate intent exists
        if intent not in self.playbook["intents"]:
            intent = "_fallback"

        # Off-hours routing: redirect non-emergency to _after_hours
        actual_intent = intent
        if (
            self.time_window is not None
            and self.time_window != "office_hours"
            and intent != "emergency"
            and "_after_hours" in self.playbook["intents"]
        ):
            self.requested_intent = intent
            actual_intent = "_after_hours"
        else:
            self.requested_intent = None

        self.current_intent = actual_intent
        self.current_step_index = 0

        return self._dispatch_first_step()

    def switch_intent(self, new_intent: str, session) -> str:
        """Mid-call intent change. Carries forward shared fields."""

        # Validate
        valid_intents = [k for k in self.playbook["intents"] if not k.startswith("_")]
        if new_intent not in self.playbook["intents"]:
            return f"Invalid intent '{new_intent}'. Valid intents: {', '.join(valid_intents)}"

        # Carry forward shared fields
        shared_fields = {}
        for field in ["name", "phone"]:
            if field in self.collected:
                shared_fields[field] = self.collected[field]

        # Off-hours routing applies to switches too
        actual_intent = new_intent
        if (
            self.time_window is not None
            and self.time_window != "office_hours"
            and new_intent != "emergency"
            and "_after_hours" in self.playbook["intents"]
        ):
            self.requested_intent = new_intent
            actual_intent = "_after_hours"
        else:
            self.requested_intent = None

        # Reset for new intent
        self.current_intent = actual_intent
        self.current_step_index = 0
        self.collected = shared_fields
        self.outcome = None

        # Skip steps for already-collected shared fields
        self._skip_pre_collected_steps()

        # Build response with acknowledgment
        first_step = self._dispatch_first_step()
        return f"Say 'Of course, I can help with that.' Then: {first_step}"

    def _dispatch_first_step(self) -> str:
        """Return speech instruction for the current step (used after set/switch intent).
        Sync because first steps are always collect or speak, never action
        (enforced by compiler validation)."""
        if self.current_step_index >= len(self.current_steps):
            return "[call_ended]"
        step = self.current_steps[self.current_step_index]
        if step["type"] == "collect":
            return step["prompt"]
        if step["type"] == "speak":
            return self._format_speak_sync(step)
        # Action steps should never be first (compiler validates this)
        return f"[action:{step['fn']}]"

    def _format_speak_sync(self, step: dict) -> str:
        """Format a speak step, merging with next collect if present. Sync version."""
        if step["mode"] == "verbatim":
            text = step["text"]
            next_step = self.peek_next_step()
            if next_step and next_step["type"] == "collect":
                self.current_step_index += 1
                return f'Say EXACTLY: "{text}" Then, {next_step["prompt"]}'
            return f'Say EXACTLY: "{text}"'
        else:
            prompt = step["prompt"]
            next_step = self.peek_next_step()
            if next_step and next_step["type"] == "collect":
                self.current_step_index += 1
                return f"{prompt} Then, {next_step['prompt']}"
            return prompt

    async def update_field(self, field_name: str, value: str, session) -> str:
        if self.current_intent is None:
            return "No intent has been set yet. Call set_intent first."

        step = self.current_steps[self.current_step_index]
        if step["type"] != "collect":
            return "Current step is not a collect step."

        if step["field"] != field_name:
            # Allow overwriting a previously collected field without advancing
            if field_name in self.collected:
                self.collected[field_name] = value
                return f"Updated {field_name}. {step['prompt']}"
            return f"Expected field '{step['field']}', got '{field_name}'. Please provide {step['field']}."

        if not value.strip():
            return f"Please provide a real value for {field_name}."

        if value.strip().lower() in PLACEHOLDER_PATTERNS:
            return f"Please provide a real value for {field_name}, not a placeholder."

        if field_name == "appointment_time" and _is_incomplete_appointment_time(value):
            return f"The caller only provided a day ({value}) but not a specific time. Ask what time on {value} works for them."

        self.collected[field_name] = value
        return await self.advance(session)

    async def advance(self, session) -> str:
        self.current_step_index += 1

        if self.current_step_index >= len(self.current_steps):
            return "[call_ended]"

        return await self._dispatch_current_step(session)

    async def _dispatch_current_step(self, session) -> str:
        step = self.current_steps[self.current_step_index]

        if step["type"] == "action":
            return await self._execute_action(step, session)

        if step["type"] == "speak":
            return await self._deliver_speak(step, session)

        if step["type"] == "collect":
            return step["prompt"]

        return f"Unknown step type: {step['type']}"

    async def _deliver_speak(self, step: dict, session) -> str:
        if step["mode"] == "verbatim":
            text = step["text"]
            next_step = self.peek_next_step()
            if next_step and next_step["type"] == "collect":
                self.current_step_index += 1
                return f'Say EXACTLY: "{text}" Then, {next_step["prompt"]}'
            return f'Say EXACTLY: "{text}"'
        else:  # guided
            prompt = step["prompt"]
            next_step = self.peek_next_step()
            if next_step and next_step["type"] == "collect":
                self.current_step_index += 1
                return f"{prompt} Then, {next_step['prompt']}"
            return prompt

    async def _execute_action(self, step: dict, session) -> str:
        fn_name = step["fn"]
        fn = ACTION_REGISTRY.get(fn_name)
        if fn is None:
            return f"Unknown action function: {fn_name}"
        return await fn(self, session)
