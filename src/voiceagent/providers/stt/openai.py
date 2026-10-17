import time

import httpx

from voiceagent.providers.base import Transcript


class OpenAISTT:
    def __init__(self, api_key: str, model: str = "whisper-1") -> None:
        self.api_key = api_key
        self.model = model
        self.name = f"openai:{model}"

    async def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav") -> Transcript:
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={"model": self.model, "language": "tr"},
                files={"file": ("audio.wav", audio, mime_type)},
            )
        resp.raise_for_status()
        return Transcript(text=resp.json()["text"], latency_s=time.perf_counter() - start)
