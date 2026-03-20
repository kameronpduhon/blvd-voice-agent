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
from src.post_call import post_summary
from src.step_executor import StepExecutor
from src.utils import detect_time_window

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self, playbook: dict):
        self.executor = StepExecutor(playbook)
        self.playbook = playbook
        super().__init__(instructions=playbook["system_prompt"])

    async def on_enter(self) -> None:
        # TODO: respect playbook greeting mode (verbatim for now)
        greeting = self.playbook["scripts"]["greeting"]
        await self.session.say(greeting)

    @function_tool()
    async def set_intent(self, context: RunContext, intent: str) -> str:
        """Identify what the caller needs. Call this once after the greeting.

        Args:
            intent: The caller's intent (e.g. "routine_service")
        """
        result = await self.executor.set_intent(intent, self.session)
        if "[call_ended]" in result:
            await context.wait_for_playout()
            self.session.shutdown()
        return result

    @function_tool()
    async def update_field(
        self, context: RunContext, field_name: str, value: str
    ) -> str:
        """Record information the caller provided. Use the EXACT field name
        from the current step prompt.

        Args:
            field_name: The exact field name for the current step (e.g. "name", "phone", "address")
            value: The caller's actual response. NEVER use placeholders.
        """
        result = await self.executor.update_field(field_name, value, self.session)
        if "[call_ended]" in result:
            await context.wait_for_playout()
            self.session.shutdown()
        return result


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="acme-hvac-agent")
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    playbook = load_playbook()

    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="multi"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(model="deepgram/aura-2", voice="andromeda"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    agent = Assistant(playbook)
    agent.executor.time_window = detect_time_window(playbook)
    agent.executor.call_start_time = time.time()

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
            agent.executor.transcript += f"{role}: {text}\n"

    await ctx.connect()

    # Post-call summary on disconnect
    @ctx.room.on("participant_disconnected")
    def on_disconnect(participant):
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            asyncio.create_task(post_summary(agent.executor, agent.executor.call_start_time))


if __name__ == "__main__":
    cli.run_app(server)
