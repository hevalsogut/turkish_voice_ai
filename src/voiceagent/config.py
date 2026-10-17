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
    llm_model: str = "gpt-4.1-mini"
    tts_model: str = "eleven_flash_v2_5"
    tts_voice_id: str = ""

    clinic_dir: str = "data/clinics/demo"
    handoff_path: str = "data/handoffs.jsonl"


def get_settings() -> Settings:
    return Settings()
