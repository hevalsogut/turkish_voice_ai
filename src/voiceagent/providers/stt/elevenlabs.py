import time

import httpx

from voiceagent.providers.base import Transcript


class ElevenLabsSTT:
    def __init__(self, api_key: str, model: str = "scribe_v1") -> None:
        self.api_key = api_key
        self.model = model
        self.name = f"elevenlabs:{model}"

    async def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav") -> Transcript:
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers={"xi-api-key": self.api_key},
                data={"model_id": self.model, "language_code": "tur"},
                files={"file": ("audio.wav", audio, mime_type)},
            )
        resp.raise_for_status()
        return Transcript(text=resp.json()["text"], latency_s=time.perf_counter() - start)
