from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepgram_api_key: str = ""
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""

    deepgram_model: str = "nova-3"
    openai_stt_model: str = "whisper-1"
    elevenlabs_stt_model: str = "scribe_v1"


def get_settings() -> Settings:
    return Settings()
