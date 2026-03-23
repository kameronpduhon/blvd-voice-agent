import logging

from src.actions import ACTION_REGISTRY

logger = logging.getLogger("agent")

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

    async def set_intent(self, intent: str, session) -> str:
        if self.current_intent is not None:
            return "Intent has already been set. Continue with update_field."

        if intent not in self.playbook["intents"]:
            intent = "_fallback"

        # Off-hours routing: redirect non-emergency to _after_hours
        if (
            self.time_window is not None
            and self.time_window != "office_hours"
            and intent != "emergency"
        ):
            if "_after_hours" in self.playbook["intents"]:
                self.requested_intent = intent
                intent = "_after_hours"
            else:
                logger.warning(
                    "Off-hours call but no _after_hours intent configured — running normal flow"
                )

        self.current_intent = intent
        self.current_step_index = 0
        return await self._dispatch_current_step(session)

    async def update_field(self, field_name: str, value: str, session) -> str:
        if self.current_intent is None:
            return "No intent set. Call set_intent first."

        step = self.current_steps[self.current_step_index]
        if step["type"] != "collect":
            return "Current step is not a collect step."

        if step["field"] != field_name:
            # Allow overwriting a previously collected field without advancing
            if field_name in self.collected:
                self.collected[field_name] = value
                return f"Updated {field_name}. {step['prompt']}"
            return f"Expected field '{step['field']}', got '{field_name}'. Please provide {step['field']}."

        if value.strip().lower() in PLACEHOLDER_PATTERNS:
            return f"Please provide a real value for {field_name}, not a placeholder."

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
