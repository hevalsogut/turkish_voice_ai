import time

import httpx

from voiceagent.providers.base import Transcript


class DeepgramSTT:
    def __init__(self, api_key: str, model: str = "nova-3") -> None:
        self.api_key = api_key
        self.model = model
        self.name = f"deepgram:{model}"

    async def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav") -> Transcript:
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params={"model": self.model, "language": "tr", "smart_format": "true"},
                headers={"Authorization": f"Token {self.api_key}", "Content-Type": mime_type},
                content=audio,
            )
        resp.raise_for_status()
        latency = time.perf_counter() - start
        alt = resp.json()["results"]["channels"][0]["alternatives"][0]
        return Transcript(text=alt["transcript"], latency_s=latency)
