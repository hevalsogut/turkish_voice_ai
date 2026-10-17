"""LiveKit worker entrypoint.

Talk to it locally in the terminal:   python -m voiceagent.agent.main console
Run as a worker (browser / phone):    python -m voiceagent.agent.main dev
"""

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from livekit.agents import AgentSession, JobContext, WorkerOptions, cli, metrics
from livekit.plugins import silero

from voiceagent.agent.clinic_agent import ClinicAgent
from voiceagent.agent.factory import build_llm, build_stt, build_tts
from voiceagent.agent.prompts import greeting_instruction
from voiceagent.clinic.handoff import JsonlNotifier
from voiceagent.clinic.loader import load_clinic
from voiceagent.clinic.scheduler import InMemoryAppointmentStore
from voiceagent.config import get_settings

latency_log = logging.getLogger("voiceagent.latency")


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

    @session.on("metrics_collected")
    def _log_latency(ev) -> None:
        m = ev.metrics
        if isinstance(m, metrics.EOUMetrics):
            latency_log.info("LATENCY end_of_utterance=%.2fs transcript=%.2fs",
                             m.end_of_utterance_delay, m.transcription_delay)
        elif isinstance(m, metrics.LLMMetrics):
            latency_log.info("LATENCY llm_first_token=%.2fs", m.ttft)
        elif isinstance(m, metrics.TTSMetrics):
            latency_log.info("LATENCY tts_first_audio=%.2fs", m.ttfb)

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
