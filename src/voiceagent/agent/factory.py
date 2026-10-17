"""Builds the STT / LLM / TTS components from settings. The only place vendors are named."""

from livekit.plugins import deepgram, elevenlabs, openai

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


def build_llm(settings: Settings):
    return openai.LLM(model=settings.llm_model, api_key=settings.openai_api_key)


def build_tts(settings: Settings):
    kwargs = {"voice_id": settings.tts_voice_id} if settings.tts_voice_id else {}
    return elevenlabs.TTS(
        model=settings.tts_model,
        language="tr",
        api_key=settings.elevenlabs_api_key,
        **kwargs,
    )
