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
    def __init__(self, playbook: dict, intent: str, pre_collected: dict | None = None):
        self.playbook = playbook
        self.current_intent: str = intent
        self.current_step_index: int = 0
        self.collected: dict[str, str] = {}
        self.transcript: str = ""
        self.outcome: str | None = None
        self.time_window: str | None = None
        self.call_start_time: float | None = None
        self.requested_intent: str | None = None

        # Pre-populate fields carried from a previous agent (e.g., name, phone)
        if pre_collected:
            for field, value in pre_collected.items():
                self.collected[field] = value
            self._skip_pre_collected_steps()

    def _skip_pre_collected_steps(self):
        """Skip past collect steps for fields that are already in self.collected."""
        while self.current_step_index < len(self.current_steps):
            step = self.current_steps[self.current_step_index]
            if step["type"] == "collect" and step["field"] in self.collected:
                self.current_step_index += 1
            else:
                break

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

    async def update_field(self, field_name: str, value: str, session) -> str:
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
