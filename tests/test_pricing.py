from voiceagent.pricing import llm_cost, realtime_cost, stt_cost


def test_realtime_cost_uses_audio_rates_and_cache_discount():
    # 1M fresh audio in + 1M audio out on gpt-realtime-2.1 = $32 + $64
    cost = realtime_cost(
        "gpt-realtime-2.1", audio_in=1_000_000, text_in=0, cached_audio=0, cached_text=0,
        audio_out=1_000_000, text_out=0,
    )
    assert cost == 96
    cached = realtime_cost(
        "gpt-realtime-2.1", audio_in=1_000_000, text_in=0, cached_audio=1_000_000, cached_text=0,
        audio_out=0, text_out=0,
    )
    assert cached == 0.4


def test_unknown_model_has_no_price_instead_of_a_guess():
    assert realtime_cost("mystery", audio_in=1, text_in=1, cached_audio=0, cached_text=0,
                         audio_out=1, text_out=1) is None
    assert llm_cost("gpt-4.1-mini", prompt_tokens=10, cached_tokens=0, completion_tokens=10) is None


def test_gpt41_and_stt_cost():
    assert llm_cost("gpt-4.1", prompt_tokens=1_000_000, cached_tokens=0, completion_tokens=0) == 2
    assert round(stt_cost(60), 4) == 0.0058
