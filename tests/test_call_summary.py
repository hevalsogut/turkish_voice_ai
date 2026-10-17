from voiceagent.web.app import _summarize


def ev(t, kind, **kw):
    return {"t": f"2026-10-17T10:{t}+00:00", "kind": kind, **kw}


def test_realtime_cost_is_sum_of_usage():
    events = [
        ev("00:00", "start", engine="realtime", model="gpt-realtime-2.1"),
        ev("00:30", "usage", part="realtime", usd=0.02),
        ev("01:00", "usage", part="realtime", usd=0.03),
        ev("02:00", "end"),
    ]
    s = _summarize(events)
    assert s["engine"] == "realtime" and s["usd"] == 0.05 and s["minutes"] == 2.0


def test_classic_cost_adds_stt_and_reports_voice_characters():
    events = [
        ev("00:00", "start", engine="classic", model="gpt-4.1 + deepgram + elevenlabs"),
        ev("00:10", "usage", part="llm", usd=0.01),
        ev("00:11", "usage", part="tts", characters=120),
        ev("01:00", "end"),
    ]
    s = _summarize(events)
    assert s["tts_characters"] == 120
    assert s["usd"] == round(0.01 + 0.0058, 4)


def test_unpriced_model_gives_no_dollar_figure():
    events = [ev("00:00", "start", engine="classic"), ev("00:10", "usage", part="llm", usd=None)]
    assert _summarize(events)["usd"] is None
