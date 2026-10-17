"""LiveKit worker entrypoint.

Talk to it locally in the terminal:   python -m voiceagent.agent.main console
Run as a worker (dashboard / phone):  python -m voiceagent.agent.main dev
The clinic config is re-read for every call, so dashboard edits apply to the next call.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from livekit.agents import AgentSession, JobContext, WorkerOptions, cli, metrics
from livekit.plugins import silero

from voiceagent.agent.clinic_agent import ClinicAgent
from voiceagent.agent.factory import build_llm, build_stt, build_tts
from voiceagent.agent.prompts import greeting_instruction
from voiceagent.agent.recorder import CallRecorder
from voiceagent.clinic.handoff import JsonlNotifier
from voiceagent.clinic.loader import load_clinic
from voiceagent.clinic.sqlite_store import SqliteAppointmentStore
from voiceagent.config import get_settings

latency_log = logging.getLogger("voiceagent.latency")


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    config, knowledge = load_clinic(Path(settings.clinic_dir))
    tz = ZoneInfo(config.timezone)
    store = SqliteAppointmentStore(config, Path(settings.db_path), lambda: datetime.now(tz))

    await ctx.connect()
    session = AgentSession(
        stt=build_stt(settings),
        llm=build_llm(settings, config.agent),
        tts=build_tts(settings, config.agent),
        vad=silero.VAD.load(),
    )

    recorder = CallRecorder(Path(settings.calls_dir), ctx.room.name)

    def publish(event: dict) -> None:
        """Send a live event to the dashboard and record it in the call history."""
        recorder.add(event["type"], **{k: v for k, v in event.items() if k != "type"})
        payload = json.dumps(event, ensure_ascii=False).encode("utf-8")
        asyncio.ensure_future(
            ctx.room.local_participant.publish_data(payload, reliable=True, topic="agent-events")
        )

    @session.on("metrics_collected")
    def _on_metrics(ev) -> None:
        m = ev.metrics
        if isinstance(m, metrics.EOUMetrics):
            latency_log.info("LATENCY end_of_utterance=%.2fs", m.end_of_utterance_delay)
            publish(
                {"type": "latency", "stage": "end_of_turn", "seconds": m.end_of_utterance_delay}
            )
        elif isinstance(m, metrics.LLMMetrics):
            latency_log.info("LATENCY llm_first_token=%.2fs", m.ttft)
            publish({"type": "latency", "stage": "llm", "seconds": m.ttft})
        elif isinstance(m, metrics.TTSMetrics):
            latency_log.info("LATENCY tts_first_audio=%.2fs", m.ttfb)
            publish({"type": "latency", "stage": "tts", "seconds": m.ttfb})

    @session.on("conversation_item_added")
    def _on_item(ev) -> None:
        item = ev.item
        if item.type == "message" and item.text_content:
            recorder.add("message", role=item.role, text=item.text_content)

    @session.on("close")
    def _on_close(ev) -> None:
        recorder.add("end")

    agent = ClinicAgent(
        config=config,
        knowledge=knowledge,
        store=store,
        notifier=JsonlNotifier(Path(settings.handoff_path)),
        on_event=publish,
        on_hangup=lambda: asyncio.ensure_future(ctx.delete_room()),
    )
    await session.start(room=ctx.room, agent=agent)
    await session.generate_reply(instructions=greeting_instruction(config, datetime.now(tz)))


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, port=get_settings().worker_port))
