"""
Phase 0 — Gemini Live Native Audio Proof of Concept

Minimal agent to verify:
  1. Greeting trigger (system prompt alone vs generate_reply)
  2. Voice quality over SIP
  3. Function tool calling works
  4. Turn detection / noise cancellation

Test:
  uv run python poc_agent.py console
  uv run python poc_agent.py dev       # then call (555) 100-2000

Env: GOOGLE_API_KEY must be set in .env.local
"""

import logging

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool, room_io
from livekit.plugins import google, noise_cancellation, silero

load_dotenv(".env.local")

logger = logging.getLogger("poc-agent")


class POCAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Julie, a friendly and professional HVAC receptionist for Acme H-vac "
                "in our service area. Greet the caller warmly and ask how you can help.\n\n"
                "If the caller asks about company hours, answer directly:\n"
                "- Office hours: Monday through Friday, 8 AM to 5 PM\n"
                "- On-call hours: 5 PM to 10 PM for emergencies\n\n"
                "If the caller asks about hours, use the get_company_hours tool to get the details.\n\n"
                "Keep responses brief and natural — you are speaking on the phone, not writing an essay.\n"
                "Do NOT use markdown, bullet points, or emojis in your responses."
            ),
        )

    @function_tool()
    async def get_company_hours(self, context: RunContext) -> str:
        """Get the company's business hours. Call this when the caller asks about hours."""
        return (
            "Office hours: Monday through Friday, 8 AM to 5 PM. "
            "On-call hours for emergencies: 5 PM to 10 PM daily."
        )


server = AgentServer()


def prewarm(proc: agents.JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="poc-gemini-live")
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-12-2025",
            voice="Kore",
            temperature=0.8,
        ),
        vad=ctx.proc.userdata["vad"],
    )

    await session.start(
        agent=POCAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Transcript capture
    @session.on("conversation_item_added")
    def on_conversation_item(ev):
        text = ev.item.text_content
        if text:
            role = "Caller" if ev.item.role == "user" else "Agent"
            logger.info(f"[transcript] {role}: {text}")

    await ctx.connect()

    # --- Greeting trigger ---
    # Option A: Comment out the line below to test if model greets from system prompt alone.
    # Option B: Explicit trigger (use if Option A is unreliable):
    session.generate_reply(instructions="Greet the caller now using the greeting from your instructions.")


if __name__ == "__main__":
    agents.cli.run_app(server)
