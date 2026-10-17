import pytest

from voiceagent.agent.factory import build_tts, tts_provider_name
from voiceagent.clinic.models import AgentSettings
from voiceagent.config import Settings

S = Settings(_env_file=None, openai_api_key="x", elevenlabs_api_key="y")


def test_default_provider_is_elevenlabs():
    assert tts_provider_name(S) == "elevenlabs"


def test_clinic_override_selects_openai_and_valid_voice():
    agent = AgentSettings(tts_provider="openai", tts_voice_id="cedar")
    assert tts_provider_name(S, agent) == "openai"
    tts = build_tts(S, agent)
    assert type(tts).__module__.startswith("livekit.plugins.openai")


def test_unknown_openai_voice_falls_back_instead_of_failing():
    build_tts(S, AgentSettings(tts_provider="openai", tts_voice_id="not-a-voice"))


def test_unsupported_provider_raises():
    with pytest.raises(ValueError):
        build_tts(S, AgentSettings(tts_provider="nope"))
