"""Provider interfaces.

Every external dependency (STT, LLM, TTS, telephony) sits behind one of these
protocols so a vendor can be swapped, or self-hosted later, via configuration only.
Streaming variants are added in Phase 1 alongside the LiveKit agent.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str = "tr"
    latency_s: float = 0.0


@runtime_checkable
class STTProvider(Protocol):
    name: str

    async def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav") -> Transcript:
        """Transcribe a complete audio clip (batch). Used for benchmarking."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def complete(self, system: str, messages: list[dict[str, str]]) -> str: ...


@runtime_checkable
class TTSProvider(Protocol):
    name: str

    async def synthesize(self, text: str) -> bytes: ...
