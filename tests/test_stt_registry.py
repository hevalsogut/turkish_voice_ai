from voiceagent.config import Settings
from voiceagent.providers.base import STTProvider
from voiceagent.providers.stt import available_stt_providers


def test_only_configured_providers_are_returned():
    providers = available_stt_providers(Settings(_env_file=None, deepgram_api_key="x"))
    assert list(providers) == ["deepgram"]
    assert isinstance(providers["deepgram"], STTProvider)


def test_no_keys_no_providers():
    assert available_stt_providers(Settings(_env_file=None)) == {}
