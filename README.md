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
