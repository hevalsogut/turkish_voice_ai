# Voice Agent (working name)

Turkish-language AI voice agent for businesses. First target: clinic appointment calls.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add API keys
pytest && ruff check src tests
```

## Architecture rule

STT, LLM, TTS and telephony each sit behind a protocol in `src/voiceagent/providers/base.py`.
Vendors are swappable (or self-hosted later) by configuration, never by touching agent logic.

## Phase 0: Turkish STT bake-off

Goal: pick the STT provider with real phone-quality Turkish audio, not clean mic audio.

1. Record yourself reading each line of `data/stt_bench/script.tr.txt` (phone voice memo is fine).
   Name files `01.wav` ... `20.wav` (m4a/mp3 also work). Better: have 2-3 different speakers
   and add some background noise for a few clips.
2. Convert to phone quality:
   `voiceagent telephonize ~/recordings data/stt_bench/clips`
3. Build the manifest: `voiceagent make-manifest`
4. Run: `voiceagent stt-bench` (add `--only deepgram` to restrict)

Output: WER / CER / p50 latency per provider; per-clip detail in `data/stt_bench/results/latest.jsonl`.
Read the per-clip file too: names, numbers, and dates matter most for appointments.

## Phase 1: talk to the clinic agent

```bash
python -m voiceagent.agent.main console   # speak through your Mac's mic and speakers
```

- Clinic data lives in `data/clinics/demo/` (`clinic.yaml` for hours/departments, `knowledge.md` for FAQs).
- Bookings are in memory for now (lost on restart). Staff handoffs are appended to `data/handoffs.jsonl`.
- Swap vendors in `.env` (`STT_PROVIDER`, `LLM_MODEL`, `TTS_MODEL`, `TTS_VOICE_ID`); only
  `src/voiceagent/agent/factory.py` names vendors.
- Phone numbers are validated and read back by code (`clinic/phone.py`), never by the LLM.
- Latency (measured from this machine): ElevenLabs flash first audio ~0.26s, LLM first token ~0.6s,
  plus ~0.3-0.5s end-of-turn detection. Per-turn timings are logged as `LATENCY ...`.
- `gpt-4o-mini` booked the wrong slot in testing, `gpt-4.1` is the default: it understands "ona doğru" (around ten) correctly where `gpt-4.1-mini` picked nine, at the same latency.
- Console logs (`data/console.log`) contain call transcripts and are git-ignored.

## Dashboard (configure + test)

```bash
voiceagent dev        # starts the voice server, the voice worker and the dashboard
# open http://127.0.0.1:8000
```

Needs `brew install livekit` once (local real-time media server). Pages: Test call (voice in the
browser, or text), Agent settings (clinic, voice, models, extra instructions), Knowledge base
(editable Markdown), Appointments, Staff messages. Edits apply to the next call.
The dashboard has no login and binds to 127.0.0.1 only: never expose it publicly as is.
Logs: `data/logs/`.
