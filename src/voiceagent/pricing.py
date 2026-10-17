"""Cost estimates for the engine comparison. Prices are USD, from vendor pages checked 2026-10-17.

Treat results as estimates: vendors change prices. Anything without a verified price returns None
rather than a guess (ElevenLabs depends on your plan; non-gpt-4.1 text models are not listed).
"""

# USD per 1M tokens. Source: developers.openai.com/api/docs/models/<model>
REALTIME_PRICES: dict[str, dict[str, float]] = {
    "gpt-realtime-2.1": {
        "text_in": 4, "text_cached": 0.4, "text_out": 24,
        "audio_in": 32, "audio_cached": 0.4, "audio_out": 64,
    },
    "gpt-realtime-2.1-mini": {
        "text_in": 0.6, "text_cached": 0.06, "text_out": 2.4,
        "audio_in": 10, "audio_cached": 0.3, "audio_out": 20,
    },
}
GPT_41 = {"input": 2.0, "cached": 0.5, "output": 8.0}  # USD per 1M tokens
DEEPGRAM_NOVA3_PER_MIN = 0.0058  # multilingual streaming rate; monolingual is currently cheaper


def realtime_cost(
    model: str,
    *,
    audio_in: int, text_in: int, cached_audio: int, cached_text: int,
    audio_out: int, text_out: int,
) -> float | None:
    p = REALTIME_PRICES.get(model)
    if p is None:
        return None
    per = 1_000_000
    return (
        max(audio_in - cached_audio, 0) * p["audio_in"]
        + cached_audio * p["audio_cached"]
        + max(text_in - cached_text, 0) * p["text_in"]
        + cached_text * p["text_cached"]
        + audio_out * p["audio_out"]
        + text_out * p["text_out"]
    ) / per


def llm_cost(
    model: str, *, prompt_tokens: int, cached_tokens: int, completion_tokens: int
) -> float | None:
    if model != "gpt-4.1":
        return None
    per = 1_000_000
    fresh = max(prompt_tokens - cached_tokens, 0)
    return (
        fresh * GPT_41["input"] + cached_tokens * GPT_41["cached"]
        + completion_tokens * GPT_41["output"]
    ) / per


def stt_cost(audio_seconds: float) -> float:
    return audio_seconds / 60 * DEEPGRAM_NOVA3_PER_MIN
