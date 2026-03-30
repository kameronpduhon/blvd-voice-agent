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
    RunContext,
    cli,
    function_tool,
    room_io,
)
from livekit.plugins import google, noise_cancellation, silero

from src.playbook import load_playbook
from src.post_call import post_summary_from_userdata
from src.step_executor import StepExecutor
from src.utils import detect_time_window

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class AcmeHVACAgent(Agent):
    def __init__(self, playbook: dict, time_window: str):
        self.playbook = playbook
        self.executor = StepExecutor(playbook)
        self.executor.time_window = time_window

        # Inject time_window into system prompt for greeting selection
        prompt = playbook["system_prompt"].replace("TIME_WINDOW_PLACEHOLDER", time_window)
        super().__init__(instructions=prompt)

    @function_tool()
    async def set_intent(self, context: RunContext, intent: str) -> str:
        """Identify the caller's need and start the appropriate flow. Call this once after greeting.

        Args:
            intent: The caller's intent (e.g. "routine_service", "emergency", "cancellation")
        """
        result = self.executor.set_intent(intent, context.session)
        # Sync to userdata
        context.session.userdata["intent"] = self.executor.current_intent
        context.session.userdata["requested_intent"] = self.executor.requested_intent
        return result

    @function_tool()
    async def update_field(
        self, context: RunContext, field_name: str, value: str
    ) -> str:
        """Record information the caller provided. Use the EXACT field name from the current step prompt.

        Args:
            field_name: The exact field name for the current step
            value: The caller's actual response. NEVER use placeholders.
        """
        result = await self.executor.update_field(field_name, value, context.session)

        # Sync collected data to session userdata
        context.session.userdata["collected"] = self.executor.collected
        context.session.userdata["outcome"] = self.executor.outcome

        if "[call_ended]" in result:
            await context.wait_for_playout()
            context.session.shutdown()
        return result

    @function_tool()
    async def switch_intent(self, context: RunContext, new_intent: str) -> str:
        """Route the caller to a different intent when they ask for something outside this flow.
        For example, if during routine_service the caller says "actually I need to cancel."

        Args:
            new_intent: The intent to route to (e.g. "cancellation", "emergency")
        """
        result = self.executor.switch_intent(new_intent, context.session)
        context.session.userdata["intent"] = self.executor.current_intent
        context.session.userdata["requested_intent"] = self.executor.requested_intent
        return result


server = AgentServer()


def prewarm(proc):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="acme-hvac-agent")
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    playbook = load_playbook()
    time_window = detect_time_window(playbook)
    call_start_time = time.time()

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-12-2025",
            voice="Kore",
            temperature=0.8,
        ),
        vad=ctx.proc.userdata["vad"],
        userdata={
            "intent": None,
            "requested_intent": None,
            "time_window": time_window,
            "collected": {},
            "transcript": "",
            "outcome": None,
        },
    )

    agent = AcmeHVACAgent(playbook, time_window)

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

    # Transcript capture — may be delayed with native audio
    @session.on("conversation_item_added")
    def on_conversation_item(ev):
        text = ev.item.text_content
        if text:
            role = "Caller" if ev.item.role == "user" else "Agent"
            session.userdata["transcript"] += f"{role}: {text}\n"

    await ctx.connect()

    # Greeting trigger — model needs explicit nudge to start speaking
    session.generate_reply(
        instructions="Greet the caller now using the greeting from your instructions."
    )

    # Post-call summary on disconnect — delayed to allow transcript to settle
    _background_tasks: set[asyncio.Task] = set()

    @ctx.room.on("participant_disconnected")
    def on_disconnect(participant):
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:

            async def delayed_summary():
                await asyncio.sleep(10)  # Let transcript events settle
                await post_summary_from_userdata(session.userdata, call_start_time)

            task = asyncio.create_task(delayed_summary())
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)


if __name__ == "__main__":
    cli.run_app(server)
