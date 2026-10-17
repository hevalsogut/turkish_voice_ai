"""Builds the STT / LLM / TTS components. The only place vendors are named.

Per-clinic overrides (clinic.yaml `agent:` section) win over the global defaults in .env.
"""

from livekit.plugins import deepgram, elevenlabs, openai
from openai.types.realtime import AudioTranscription

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


# OpenAI's voices are English-optimised; this steers gpt-4o-mini-tts toward natural Turkish.
DEFAULT_TTS_INSTRUCTIONS = (
    "Speak natural, native Istanbul Turkish with no foreign accent. You are a warm, calm "
    "and professional clinic receptionist on the phone. Conversational pace with short "
    "natural pauses, never an announcer or audiobook reading tone."
)
OPENAI_VOICES = [
    "marin", "cedar", "coral", "sage", "ballad", "verse", "alloy", "ash", "echo", "fable",
    "nova", "onyx", "shimmer",
]


def tts_provider_name(settings: Settings, agent: AgentSettings | None = None) -> str:
    return (agent.tts_provider if agent else "") or settings.tts_provider


def build_tts(settings: Settings, agent: AgentSettings | None = None):
    provider = tts_provider_name(settings, agent)
    voice = (agent.tts_voice_id if agent else "") or ""
    if provider == "openai":
        instructions = (agent.tts_instructions if agent else "").strip() or DEFAULT_TTS_INSTRUCTIONS
        return openai.TTS(
            model=settings.openai_tts_model,
            voice=voice if voice in OPENAI_VOICES else "marin",
            instructions=instructions,
            api_key=settings.openai_api_key,
        )
    if provider != "elevenlabs":
        raise ValueError(f"Unsupported tts_provider: {provider}")
    voice = voice or settings.tts_voice_id
    model = (agent.tts_model if agent else "") or settings.tts_model
    kwargs = {"voice_id": voice} if voice else {}
    return elevenlabs.TTS(
        model=model, language="tr", api_key=settings.elevenlabs_api_key, **kwargs
    )


# Voices the Realtime API accepts (a subset of the TTS voices).
REALTIME_VOICES = [v for v in OPENAI_VOICES if v not in ("fable", "nova", "onyx")]
REALTIME_MODELS = ["gpt-realtime-2.1", "gpt-realtime-2.1-mini"]

# Realtime has no separate voice-style parameter, so accent and pace are steered in the prompt.
def realtime_prompt_suffix(agent_name: str) -> str:
    return f"""

# Ses ve dil
Adın {agent_name}. Kendini tanıtırken yalnızca bu ismi kullan; başka bir isim söyleme.
Her zaman Türkçe konuş; arayan başka dilde konuşmadıkça asla İngilizceye geçme. Aksansız, doğal İstanbul Türkçesiyle, sakin ve rahat bir telefon tempoyla konuş. Cümlelerin arasında kısa, doğal duraklamalar yap; spiker gibi okuma."""


def engine_name(settings: Settings, agent: AgentSettings | None = None) -> str:
    return (agent.engine if agent else "") or settings.engine


def realtime_model_name(settings: Settings, agent: AgentSettings | None = None) -> str:
    return (agent.realtime_model if agent else "") or settings.realtime_model


def build_realtime(settings: Settings, agent: AgentSettings | None = None, model: str = ""):
    voice = (agent.tts_voice_id if agent else "") or ""
    return openai.realtime.RealtimeModel(
        model=model or realtime_model_name(settings, agent),
        voice=voice if voice in REALTIME_VOICES else "marin",
        input_audio_transcription=AudioTranscription(model="gpt-4o-mini-transcribe", language="tr"),
        api_key=settings.openai_api_key,
    )
