import asyncio
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so `from src.x import y` works
# when running as `python src/agent.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    inference,
    room_io,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from src.playbook import load_playbook
from src.post_call import post_summary_from_userdata
from src.step_executor import StepExecutor
from src.utils import detect_time_window

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class RouterAgent(Agent):
    def __init__(self, playbook: dict, time_window: str | None = None):
        self.playbook = playbook
        self.time_window = time_window
        super().__init__(instructions=playbook["router_prompt"])

    async def on_enter(self) -> None:
        # Check if this is an escalation re-entry — skip greeting and route directly
        escalation = self.session.userdata.get("escalation_requested")
        if escalation:
            pre_collected = self.session.userdata.get("pre_collected")
            # Clear escalation state so it doesn't loop
            self.session.userdata["escalation_requested"] = None
            self.session.userdata["pre_collected"] = None
            # Route directly to the requested intent
            self._route(escalation, pre_collected)
            return

        scripts = self.playbook["scripts"]
        if (
            self.time_window is not None
            and self.time_window != "office_hours"
            and "after_hours_greeting" in scripts
        ):
            greeting = scripts["after_hours_greeting"]
        else:
            greeting = scripts["greeting"]
        await self.session.say(greeting)

    def _route(self, intent: str, pre_collected: dict | None = None):
        """Internal routing logic shared by route_to_intent tool and escalation re-entry."""
        if intent not in self.playbook["intents"]:
            intent = "_fallback"

        # Off-hours routing: redirect non-emergency to _after_hours
        actual_intent = intent
        requested_intent = None
        if (
            self.time_window is not None
            and self.time_window != "office_hours"
            and intent != "emergency"
            and "_after_hours" in self.playbook["intents"]
        ):
            requested_intent = intent
            actual_intent = "_after_hours"

        # Store routing info in session userdata for post-call summary
        self.session.userdata["intent"] = actual_intent
        self.session.userdata["requested_intent"] = requested_intent
        self.session.userdata["time_window"] = self.time_window

        # Create and hand off to the IntentAgent
        intent_agent = IntentAgent(
            playbook=self.playbook,
            intent=actual_intent,
            time_window=self.time_window,
            requested_intent=requested_intent,
            pre_collected=pre_collected,
        )

        self.session.update_agent(intent_agent)

    @function_tool()
    async def route_to_intent(self, context: RunContext, intent: str) -> tuple:
        """Route the caller to the appropriate specialist. Call this once after identifying what the caller needs.

        Args:
            intent: The caller's intent (e.g. "routine_service", "emergency", "cancellation")
        """
        if intent not in self.playbook["intents"]:
            intent = "_fallback"

        # Off-hours routing: redirect non-emergency to _after_hours
        actual_intent = intent
        requested_intent = None
        if (
            self.time_window is not None
            and self.time_window != "office_hours"
            and intent != "emergency"
            and "_after_hours" in self.playbook["intents"]
        ):
            requested_intent = intent
            actual_intent = "_after_hours"

        # Store routing info in session userdata for post-call summary
        self.session.userdata["intent"] = actual_intent
        self.session.userdata["requested_intent"] = requested_intent
        self.session.userdata["time_window"] = self.time_window

        # Speak transfer announcement if this intent has one — must complete before handoff
        transfer_messages = self.playbook["scripts"].get("transfer_messages", {})
        if actual_intent in transfer_messages:
            await self.session.say(
                transfer_messages[actual_intent], allow_interruptions=False
            )

        # Read pre_collected from userdata (set by escalation)
        pre_collected = self.session.userdata.get("pre_collected")
        self.session.userdata["pre_collected"] = None

        # Create and hand off to the IntentAgent
        intent_agent = IntentAgent(
            playbook=self.playbook,
            intent=actual_intent,
            time_window=self.time_window,
            requested_intent=requested_intent,
            pre_collected=pre_collected,
        )

        return intent_agent, f"Routing to {actual_intent} specialist."


class IntentAgent(Agent):
    def __init__(
        self,
        playbook: dict,
        intent: str,
        time_window: str | None = None,
        requested_intent: str | None = None,
        pre_collected: dict | None = None,
    ):
        self.playbook = playbook
        self.intent = intent
        self.executor = StepExecutor(playbook, intent, pre_collected=pre_collected)
        self.executor.time_window = time_window
        self.executor.requested_intent = requested_intent

        # Use the intent-specific prompt
        super().__init__(instructions=playbook["intent_prompts"][intent])

    async def on_enter(self) -> None:
        # Speak intent greeting if this intent has one (routine_service, emergency, commercial)
        intent_greetings = self.playbook["scripts"].get("intent_greetings", {})
        if self.intent in intent_greetings:
            await self.session.say(intent_greetings[self.intent])
            # Greeting already asked for name — LLM will wait for caller's response
            # Step index stays at 0 (name collect); prompt instructs LLM not to re-ask
            return

        # No greeting — dispatch the first step and let the LLM speak it
        first_instruction = await self.executor._dispatch_current_step(self.session)
        if first_instruction:
            self.session.generate_reply(instructions=first_instruction)

    @function_tool()
    async def update_field(
        self, context: RunContext, field_name: str, value: str
    ) -> str:
        """Record information the caller provided. Use the EXACT field name from the current step prompt.

        Args:
            field_name: The exact field name for the current step
            value: The caller's actual response. NEVER use placeholders.
        """
        result = await self.executor.update_field(field_name, value, self.session)

        # Sync collected data to session userdata for cross-agent access
        self.session.userdata["collected"] = self.executor.collected
        self.session.userdata["transcript"] = self.executor.transcript
        self.session.userdata["outcome"] = self.executor.outcome

        if "[call_ended]" in result:
            await context.wait_for_playout()
            self.session.shutdown()
        return result

    @function_tool()
    async def escalate(self, context: RunContext, new_intent: str) -> tuple:
        """Transfer the caller to a different intent when they ask for something outside this flow.
        For example, if during routine_service the caller says "actually I need to cancel."

        Args:
            new_intent: The intent to transfer to (e.g. "cancellation", "emergency")
        """
        # Carry forward fields that are likely shared (name, phone)
        shared_fields = {}
        for field in ["name", "phone"]:
            if field in self.executor.collected:
                shared_fields[field] = self.executor.collected[field]

        # Store shared fields in userdata for the router to pass along
        self.session.userdata["pre_collected"] = shared_fields
        self.session.userdata["escalation_requested"] = new_intent

        router = RouterAgent(
            playbook=self.playbook,
            time_window=self.executor.time_window,
        )
        return (
            router,
            f"The caller needs help with something else. They mentioned: {new_intent}.",
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="cajun-hvac-agent")
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    playbook = load_playbook()
    time_window = detect_time_window(playbook)
    call_start_time = time.time()

    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="multi"),
        llm=inference.LLM(model="google/gemini-2.5-flash"),
        tts=inference.TTS(model="deepgram/aura-2", voice="asteria"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        userdata={
            "intent": None,
            "requested_intent": None,
            "time_window": time_window,
            "collected": {},
            "transcript": "",
            "outcome": None,
            "pre_collected": None,
            "escalation_requested": None,
        },
    )

    agent = RouterAgent(playbook, time_window)

    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Transcript capture — conversation_item_added fires for both user and agent messages
    @session.on("conversation_item_added")
    def on_conversation_item(ev):
        text = ev.item.text_content
        if text:
            role = "Caller" if ev.item.role == "user" else "Agent"
            session.userdata["transcript"] += f"{role}: {text}\n"

    await ctx.connect()

    # Post-call summary on disconnect
    _background_tasks: set[asyncio.Task] = set()

    @ctx.room.on("participant_disconnected")
    def on_disconnect(participant):
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            task = asyncio.create_task(
                post_summary_from_userdata(session.userdata, call_start_time)
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)


if __name__ == "__main__":
    cli.run_app(server)
