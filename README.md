# Voice Agent (working name)

Turkish-language AI voice agent for businesses. First target: clinic appointment calls.
The agent answers calls in Turkish, books appointments, answers questions from an editable
knowledge base, and leaves notes for staff when it cannot help.

**Status:** working local prototype with a configuration and testing dashboard. Not yet on a real
phone number, no login, one demo clinic. See [Next steps](#next-steps) and
[Open decisions](#open-decisions).

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
brew install livekit            # one-time: local real-time media server
cp .env.example .env            # then add your API keys (Deepgram, OpenAI, ElevenLabs)
voiceagent dev                  # starts media server, voice worker and dashboard
# open http://127.0.0.1:8000
```

Checks: `pytest && ruff check src tests`. Logs: `data/logs/`. Stop with Ctrl+C.

The dashboard has **no login and binds to 127.0.0.1 only**. Do not expose it publicly as it is.

## What you can do in the dashboard

| Page | Purpose |
|---|---|
| Test call | Talk to the agent in the browser (voice) or type (text). Pick the engine per call. Live transcript, response-time bars, and a list of what the agent did (availability checks, bookings, staff messages). |
| Call history | Every voice call: transcript, actions, response times, engine, estimated cost. Use it to find where the agent sounds off. |
| Agent settings | Clinic details and hours, agent name, opening line, speaking style (editable, with restore-default), extra instructions, engine and models, voice picker. |
| Knowledge base | Editable Markdown the agent answers from. |
| Appointments | Everything booked, with cancel. |
| Staff messages | What the agent could not resolve, with caller name, number and a specific summary. |

Edits apply to the **next call**. The clinic config is re-read at the start of every call.

## Engines

Chosen per call on the Test call page, or as the default in Agent settings.

- **Classic**: speech-to-text (Deepgram) + language model (OpenAI, default `gpt-4.1`) + voice
  (ElevenLabs, or OpenAI `gpt-4o-mini-tts` with steering instructions). Each stage is swappable and
  can be self-hosted later.
- **OpenAI Realtime** (`gpt-realtime-2.1`, `gpt-realtime-2.1-mini`): one model that listens and
  speaks. Same clinic data, tools and prompt. Cannot swap in your own STT/LLM; voices are OpenAI
  presets (English-optimised).

Only `src/voiceagent/agent/factory.py` names vendors.

## How it is built

```
src/voiceagent/
  agent/      worker entrypoint, ClinicAgent (tools), prompts, vendor factory, call recorder
  clinic/     config, appointment store (SQLite), staff handoff, phone-number handling
  providers/  STT provider protocol + clients (used by the STT benchmark)
  web/        FastAPI dashboard backend + static frontend (no build step)
  bench/      STT benchmark tooling
  pricing.py  cost estimates (verified vendor prices, dated)
data/clinics/demo/   clinic.yaml (hours, departments, agent settings) and knowledge.md
```

Design points worth knowing:

- **Phone numbers are validated and read back by code** (`clinic/phone.py`), in the natural Turkish
  way ("sıfır beş yüz elli dört, sıfır yirmi bir, doksan sekiz, yetmiş"). The model never reads digits.
- **Availability must come from the tool.** The prompt forbids inventing time slots, and the
  14-day calendar in the prompt marks closed days.
- **Speaking style is data, not code**: edit it in Agent settings. Fixed rules (tools, safety,
  capabilities) live in `agent/prompts.py`.
- **The agent is honest if asked whether it is a robot.** Deliberate: human-like tone is fine,
  deceiving a caller who asks directly is not.
- `end_call` returns nothing so the model does not speak after the goodbye, then hangs up the room.
- Tenant identity is not editable from the UI. Appointments are stored per `tenant_id`.

## Configuration (.env)

Only the three API keys are required. Defaults: `STT_PROVIDER=deepgram`, `LLM_MODEL=gpt-4.1`,
`TTS_PROVIDER=elevenlabs`, `TTS_MODEL=eleven_flash_v2_5`, `ENGINE=classic`,
`REALTIME_MODEL=gpt-realtime-2.1`. Per-clinic overrides set in the dashboard win over `.env`.
The voice worker uses port 8091 (8081 was taken on the dev machine); change `WORKER_PORT` if needed.

## Costs and limits (checked 2026-10-17, verify before relying on them)

- OpenAI Realtime audio, per 1M tokens in/out: `gpt-realtime-2.1` $32 / $64,
  `gpt-realtime-2.1-mini` $10 / $20. `gpt-4.1` text: $2 in, $0.5 cached, $8 out.
- Deepgram Nova-3 streaming: about $0.0058/min (multilingual), currently promotional.
- ElevenLabs: the dev account is on the **free plan: 10,000 characters/month (about 8-10 minutes
  of speech) and 3 voice slots**. Heavy testing exhausts it. Cost for Classic calls shows voice
  characters separately because ElevenLabs pricing depends on the plan.
- Call history shows an estimated cost per call, `None` where there is no verified price.

## Privacy

- `.env`, `data/calls/` (transcripts), `data/handoffs.jsonl`, `data/*.db` and logs are git-ignored
  because they can hold names and phone numbers.
- Call data goes to Deepgram, OpenAI and ElevenLabs. **KVKK (Turkish data protection law)
  compliance is not addressed yet** and must be before real customers.

## STT benchmark (not run yet)

Picks the best Turkish speech-to-text on phone-quality audio. Record the 20 sentences in
`data/stt_bench/script.tr.txt` as `01`...`20` (m4a/wav), then:

```bash
voiceagent telephonize ~/recordings data/stt_bench/clips
voiceagent make-manifest
voiceagent stt-bench            # WER / CER / latency per provider
```

## Open decisions

1. **Engine: Classic vs OpenAI Realtime.** Plan: make the same three test calls on each (normal
   booking; ask for a person and leave a message; interrupt it and give a phone number in groups),
   then compare naturalness, accent, mistakes and the per-call cost in Call history.
2. **Voice.** The saved ElevenLabs voice is still an English preset ("Bill"). Try native Turkish
   voices from the in-dashboard library (Gözde Arıkan, Ahu, Eda Atlas were the data-based
   shortlist) and OpenAI voices (marin, cedar). Realtime falls back to marin if the saved voice is
   not an OpenAI one.
3. **Agent name vs voice.** The agent is currently named Murat; keep the name and voice gender
   consistent.

## Next steps

- Run the STT benchmark with real recordings.
- Get a Turkish phone number (Turkish SIP trunk or Twilio; needs business paperwork, start early)
  and connect it through LiveKit SIP.
- Postgres (+ pgvector for retrieval when knowledge bases get large) and real multi-tenancy.
- Authentication for the dashboard; per-department schedules and doctors in the scheduler.
- KVKK: consent and disclosure, data processing agreements, retention.
- Second real customer: validate that someone other than the builder will pay.

## Known issues

- Speech-to-text can hear a word in silence (seen with a silent test microphone on Classic).
- Spoken numbers in unusual phrasing can still be misheard; the read-back confirmation catches it.
- Realtime latency in the dashboard excludes the model's wait for the caller to stop talking, so it
  is not directly comparable with Classic's total.
- Knowledge is placed in the prompt (fine for small bases; the dashboard warns above about 20,000
  tokens).
