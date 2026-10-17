from voiceagent.config import Settings
from voiceagent.providers.base import STTProvider
from voiceagent.providers.stt.deepgram import DeepgramSTT
from voiceagent.providers.stt.elevenlabs import ElevenLabsSTT
from voiceagent.providers.stt.openai import OpenAISTT


def available_stt_providers(settings: Settings) -> dict[str, STTProvider]:
    """Providers whose API keys are configured."""
    providers: dict[str, STTProvider] = {}
    if settings.deepgram_api_key:
        providers["deepgram"] = DeepgramSTT(settings.deepgram_api_key, settings.deepgram_model)
    if settings.openai_api_key:
        providers["openai"] = OpenAISTT(settings.openai_api_key, settings.openai_stt_model)
    if settings.elevenlabs_api_key:
        providers["elevenlabs"] = ElevenLabsSTT(
            settings.elevenlabs_api_key, settings.elevenlabs_stt_model
        )
    return providers
