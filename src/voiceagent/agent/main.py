"""LiveKit worker entrypoint.

Talk to it locally in the terminal:   python -m voiceagent.agent.main console
Run as a worker (dashboard / phone):  python -m voiceagent.agent.main dev
The clinic config is re-read for every call, so dashboard edits apply to the next call.
The engine ("classic" or "realtime") is chosen per call: the dashboard sends it as a participant
attribute, otherwise the clinic default applies.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from livekit.agents import AgentSession, JobContext, WorkerOptions, cli, metrics
from livekit.plugins import silero

from voiceagent import pricing
from voiceagent.agent.clinic_agent import ClinicAgent
from voiceagent.agent.factory import (
    build_llm,
    build_realtime,
    build_stt,
    build_tts,
    engine_name,
    realtime_model_name,
    realtime_prompt_suffix,
    tts_provider_name,
)
from voiceagent.agent.prompts import greeting_instruction
from voiceagent.agent.recorder import CallRecorder
from voiceagent.clinic.handoff import JsonlNotifier
from voiceagent.clinic.loader import load_clinic
from voiceagent.clinic.sqlite_store import SqliteAppointmentStore
from voiceagent.config import get_settings

latency_log = logging.getLogger("voiceagent.latency")


async def _participant_attributes(ctx: JobContext) -> dict[str, str]:
    """Settings the dashboard attached to this caller's token (engine choice)."""
    try:
        participant = await asyncio.wait_for(ctx.wait_for_participant(), timeout=3)
    except TimeoutError:  # console mode has no remote participant
        return {}
    return dict(participant.attributes)


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    config, knowledge = load_clinic(Path(settings.clinic_dir))
    tz = ZoneInfo(config.timezone)
    store = SqliteAppointmentStore(config, Path(settings.db_path), lambda: datetime.now(tz))

    await ctx.connect()
    attrs = await _participant_attributes(ctx)
    engine = attrs.get("engine") or engine_name(settings, config.agent)
    if engine not in ("classic", "realtime"):
        engine = "classic"
    realtime_model = attrs.get("realtime_model") or realtime_model_name(settings, config.agent)
    llm_model = config.agent.llm_model or settings.llm_model

    if engine == "realtime":
        session = AgentSession(llm=build_realtime(settings, config.agent, realtime_model))
        prompt_suffix = realtime_prompt_suffix(config.agent_name)
        model_label = realtime_model
    else:
        session = AgentSession(
            stt=build_stt(settings),
            llm=build_llm(settings, config.agent),
            tts=build_tts(settings, config.agent),
            vad=silero.VAD.load(),
        )
        prompt_suffix = ""
        tts_name = tts_provider_name(settings, config.agent)
        model_label = f"{llm_model} + {settings.stt_provider} + {tts_name}"

    recorder = CallRecorder(Path(settings.calls_dir), ctx.room.name)
    recorder.add("start", engine=engine, model=model_label, llm_model=llm_model)

    def publish(event: dict) -> None:
        """Send a live event to the dashboard and record it in the call history."""
        recorder.add(event["type"], **{k: v for k, v in event.items() if k != "type"})
        payload = json.dumps(event, ensure_ascii=False).encode("utf-8")
        asyncio.ensure_future(
            ctx.room.local_participant.publish_data(payload, reliable=True, topic="agent-events")
        )

    def latency(stage: str, seconds: float) -> None:
        latency_log.info("LATENCY %s=%.2fs", stage, seconds)
        publish({"type": "latency", "stage": stage, "seconds": seconds})

    @session.on("metrics_collected")
    def _on_metrics(ev) -> None:
        m = ev.metrics
        if isinstance(m, metrics.EOUMetrics):
            latency("end_of_turn", m.end_of_utterance_delay)
        elif isinstance(m, metrics.LLMMetrics):
            latency("llm", m.ttft)
            recorder.add(
                "usage", part="llm", prompt_tokens=m.prompt_tokens,
                completion_tokens=m.completion_tokens,
                usd=pricing.llm_cost(
                    llm_model, prompt_tokens=m.prompt_tokens,
                    cached_tokens=m.prompt_cached_tokens, completion_tokens=m.completion_tokens,
                ),
            )
        elif isinstance(m, metrics.TTSMetrics):
            latency("tts", m.ttfb)
            recorder.add("usage", part="tts", characters=m.characters_count)
        elif isinstance(m, metrics.RealtimeModelMetrics):
            if not m.cancelled and m.ttft >= 0:
                latency("realtime", m.ttft)
            i, o = m.input_token_details, m.output_token_details
            cached = i.cached_tokens_details
            recorder.add(
                "usage", part="realtime", input_tokens=m.input_tokens,
                output_tokens=m.output_tokens,
                usd=pricing.realtime_cost(
                    realtime_model, audio_in=i.audio_tokens, text_in=i.text_tokens,
                    cached_audio=cached.audio_tokens if cached else 0,
                    cached_text=cached.text_tokens if cached else 0,
                    audio_out=o.audio_tokens, text_out=o.text_tokens,
                ),
            )

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
        prompt_suffix=prompt_suffix,
    )
    await session.start(room=ctx.room, agent=agent)
    await session.generate_reply(instructions=greeting_instruction(config, datetime.now(tz)))


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, port=get_settings().worker_port))
