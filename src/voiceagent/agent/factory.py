"""Builds the STT / LLM / TTS components. The only place vendors are named.

Per-clinic overrides (clinic.yaml `agent:` section) win over the global defaults in .env.
"""

from livekit.plugins import deepgram, elevenlabs, openai

from voiceagent.clinic.models import AgentSettings
from voiceagent.config import Settings


def build_stt(settings: Settings):
    if settings.stt_provider == "deepgram":
        return deepgram.STT(
            model=settings.deepgram_model,
            language="tr",
            api_key=settings.deepgram_api_key,
            smart_format=True,
        )
    if settings.stt_provider == "openai":
        return openai.STT(
            model=settings.openai_stt_model, language="tr", api_key=settings.openai_api_key
        )
    raise ValueError(f"Unsupported stt_provider: {settings.stt_provider}")


def build_llm(settings: Settings, agent: AgentSettings | None = None):
    model = (agent.llm_model if agent else "") or settings.llm_model
    return openai.LLM(model=model, api_key=settings.openai_api_key)


def build_tts(settings: Settings, agent: AgentSettings | None = None):
    voice = (agent.tts_voice_id if agent else "") or settings.tts_voice_id
    model = (agent.tts_model if agent else "") or settings.tts_model
    kwargs = {"voice_id": voice} if voice else {}
    return elevenlabs.TTS(
        model=model, language="tr", api_key=settings.elevenlabs_api_key, **kwargs
    )
