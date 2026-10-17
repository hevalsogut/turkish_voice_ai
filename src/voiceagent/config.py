from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepgram_api_key: str = ""
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""

    deepgram_model: str = "nova-3"
    openai_stt_model: str = "whisper-1"
    elevenlabs_stt_model: str = "scribe_v1"

    # Live agent: which vendor/model each stage uses (swap here, not in agent code)
    stt_provider: str = "deepgram"
    llm_model: str = "gpt-4.1"
    tts_provider: str = "elevenlabs"
    tts_model: str = "eleven_flash_v2_5"
    openai_tts_model: str = "gpt-4o-mini-tts"
    engine: str = "classic"  # classic (STT + LLM + TTS) | realtime (one OpenAI speech model)
    realtime_model: str = "gpt-realtime-2.1"
    tts_voice_id: str = ""

    clinic_dir: str = "data/clinics/demo"
    handoff_path: str = "data/handoffs.jsonl"
    db_path: str = "data/app.db"
    calls_dir: str = "data/calls"

    # Local LiveKit server (`livekit-server --dev`) defaults; override for LiveKit Cloud
    livekit_url: str = "ws://127.0.0.1:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"
    web_port: int = 8000
    worker_port: int = 8091  # the voice worker's internal health server


def get_settings() -> Settings:
    return Settings()
