"""LiveKit worker entrypoint.

Talk to it locally in the terminal:   python -m voiceagent.agent.main console
Run as a worker (browser / phone):    python -m voiceagent.agent.main dev
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from livekit.agents import AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import silero

from voiceagent.agent.clinic_agent import ClinicAgent
from voiceagent.agent.factory import build_llm, build_stt, build_tts
from voiceagent.agent.prompts import greeting_instruction
from voiceagent.clinic.handoff import JsonlNotifier
from voiceagent.clinic.loader import load_clinic
from voiceagent.clinic.scheduler import InMemoryAppointmentStore
from voiceagent.config import get_settings


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    config, knowledge = load_clinic(Path(settings.clinic_dir))
    store = InMemoryAppointmentStore(config, datetime.now(ZoneInfo(config.timezone)))

    await ctx.connect()
    session = AgentSession(
        stt=build_stt(settings),
        llm=build_llm(settings),
        tts=build_tts(settings),
        vad=silero.VAD.load(),
    )
    agent = ClinicAgent(
        config=config,
        knowledge=knowledge,
        store=store,
        notifier=JsonlNotifier(Path(settings.handoff_path)),
    )
    await session.start(room=ctx.room, agent=agent)
    await session.generate_reply(instructions=greeting_instruction(config))


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
