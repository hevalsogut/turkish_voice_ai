"""Dashboard backend. Local-only for now (binds to 127.0.0.1, no auth): do not expose publicly."""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from livekit import api as lk_api
from livekit.agents import AgentSession
from pydantic import BaseModel

from voiceagent.agent.clinic_agent import ClinicAgent
from voiceagent.agent.factory import DEFAULT_TTS_INSTRUCTIONS, OPENAI_VOICES, build_llm
from voiceagent.clinic.handoff import JsonlNotifier
from voiceagent.clinic.loader import load_clinic, save_clinic, save_knowledge
from voiceagent.clinic.models import ClinicConfig
from voiceagent.clinic.sqlite_store import SqliteAppointmentStore
from voiceagent.config import get_settings

settings = get_settings()
CLINIC_DIR = Path(settings.clinic_dir)
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Voice agent dashboard")


def _store(config: ClinicConfig) -> SqliteAppointmentStore:
    tz = ZoneInfo(config.timezone)
    return SqliteAppointmentStore(config, Path(settings.db_path), lambda: datetime.now(tz))


# ---------- health ----------


@app.get("/api/health")
async def health() -> dict:
    livekit_up = False
    try:
        http_url = settings.livekit_url.replace("ws://", "http://").replace("wss://", "https://")
        async with httpx.AsyncClient(timeout=1.5) as client:
            livekit_up = (await client.get(http_url)).status_code < 500
    except httpx.HTTPError:
        pass
    return {
        "keys": {
            "deepgram": bool(settings.deepgram_api_key),
            "openai": bool(settings.openai_api_key),
            "elevenlabs": bool(settings.elevenlabs_api_key),
        },
        "livekit_server": livekit_up,
        "defaults": {
            "llm_model": settings.llm_model,
            "tts_model": settings.tts_model,
            "tts_voice_id": settings.tts_voice_id,
            "stt": f"{settings.stt_provider}:{settings.deepgram_model}",
        },
    }


# ---------- config & knowledge ----------


@app.get("/api/defaults")
def get_defaults() -> dict:
    from voiceagent.agent.prompts import DEFAULT_STYLE_GUIDE

    return {
        "style_guide": DEFAULT_STYLE_GUIDE,
        "tts_instructions": DEFAULT_TTS_INSTRUCTIONS,
        "openai_voices": OPENAI_VOICES,
    }


@app.get("/api/config")
def get_config() -> dict:
    config, _ = load_clinic(CLINIC_DIR)
    return config.model_dump(mode="json")


@app.put("/api/config")
def put_config(body: dict) -> dict:
    current, _ = load_clinic(CLINIC_DIR)
    body["tenant_id"] = current.tenant_id  # tenant identity is not editable from the UI
    try:
        config = ClinicConfig.model_validate(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    save_clinic(CLINIC_DIR, config)
    return config.model_dump(mode="json")


class KnowledgeBody(BaseModel):
    text: str


@app.get("/api/knowledge")
def get_knowledge() -> dict:
    _, knowledge = load_clinic(CLINIC_DIR)
    return {"text": knowledge}


@app.put("/api/knowledge")
def put_knowledge(body: KnowledgeBody) -> dict:
    save_knowledge(CLINIC_DIR, body.text)
    return {"text": body.text}


# ---------- appointments & staff messages ----------


@app.get("/api/appointments")
def list_appointments(include_cancelled: bool = False) -> list[dict]:
    config, _ = load_clinic(CLINIC_DIR)
    appts = _store(config).list_appointments(include_cancelled=include_cancelled)
    return [a.model_dump(mode="json") for a in appts]


@app.post("/api/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: str) -> dict:
    config, _ = load_clinic(CLINIC_DIR)
    if not _store(config).cancel(appointment_id):
        raise HTTPException(404, "Appointment not found or already cancelled")
    return {"ok": True}


@app.get("/api/handoffs")
def list_handoffs() -> list[dict]:
    path = Path(settings.handoff_path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in reversed(lines) if line.strip()]


# ---------- call history ----------


def _read_call(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@app.get("/api/calls")
def list_calls() -> list[dict]:
    directory = Path(settings.calls_dir)
    if not directory.exists():
        return []
    calls = []
    for path in sorted(directory.glob("*.jsonl"), reverse=True):
        events = _read_call(path)
        messages = [e for e in events if e["kind"] == "message"]
        calls.append(
            {
                "id": path.stem,
                "started": events[0]["t"] if events else "",
                "messages": len(messages),
                "preview": next((m["text"] for m in messages if m["role"] == "user"), ""),
                "ended": any(e["kind"] == "end" for e in events),
            }
        )
    return calls


@app.get("/api/calls/{call_id}")
def get_call(call_id: str) -> list[dict]:
    path = Path(settings.calls_dir) / f"{Path(call_id).name}.jsonl"  # .name blocks path traversal
    if not path.exists():
        raise HTTPException(404, "Call not found")
    return _read_call(path)


# ---------- ElevenLabs voices ----------

_voice_cache: dict = {"at": 0.0, "data": []}


@app.get("/api/voices")
async def voices() -> list[dict]:
    if time.time() - _voice_cache["at"] < 300 and _voice_cache["data"]:
        return _voice_cache["data"]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": settings.elevenlabs_api_key},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"ElevenLabs error {resp.status_code}")
    data = [
        {
            "voice_id": v["voice_id"],
            "name": v["name"],
            "category": v.get("category", ""),
            "labels": v.get("labels", {}),
            "description": v.get("description") or "",
        }
        for v in resp.json().get("voices", [])
    ]
    _voice_cache.update(at=time.time(), data=data)
    return data


class PreviewBody(BaseModel):
    voice_id: str
    provider: str = "elevenlabs"
    model: str = ""
    text: str = ""
    instructions: str = ""


@app.post("/api/voices/preview")
async def voice_preview(body: PreviewBody) -> Response:
    config, _ = load_clinic(CLINIC_DIR)
    text = body.text or f"Merhaba, ben {config.agent_name}. Size nasıl yardımcı olabilirim?"
    if body.provider == "openai":
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.openai_tts_model,
                    "voice": body.voice_id,
                    "input": text,
                    "instructions": body.instructions.strip() or DEFAULT_TTS_INSTRUCTIONS,
                    "response_format": "mp3",
                },
            )
        if resp.status_code != 200:
            raise HTTPException(502, f"OpenAI error {resp.status_code}: {resp.text[:200]}")
        return Response(resp.content, media_type="audio/mpeg")
    model = body.model or config.agent.tts_model or settings.tts_model
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{body.voice_id}",
            headers={"xi-api-key": settings.elevenlabs_api_key},
            json={"text": text, "model_id": model, "language_code": "tr"},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"ElevenLabs error {resp.status_code}: {resp.text[:200]}")
    return Response(resp.content, media_type="audio/mpeg")


class AddVoiceBody(BaseModel):
    public_owner_id: str
    voice_id: str
    name: str


@app.get("/api/voices/library")
async def voice_library(page: int = 0) -> dict:
    """Native Turkish voices from the ElevenLabs shared library (sample clips are free to play)."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.elevenlabs.io/v1/shared-voices",
            params={"language": "tr", "page_size": 24, "page": page, "sort": "trending"},
            headers={"xi-api-key": settings.elevenlabs_api_key},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"ElevenLabs error {resp.status_code}")
    body = resp.json()
    voices = [
        {
            "voice_id": v["voice_id"],
            "public_owner_id": v["public_owner_id"],
            "name": v["name"],
            "gender": v.get("gender") or "",
            "age": v.get("age") or "",
            "accent": v.get("accent") or "",
            "use_case": v.get("use_case") or "",
            "preview_url": v.get("preview_url") or "",
        }
        for v in body.get("voices", [])
    ]
    return {"voices": voices, "has_more": bool(body.get("has_more"))}


@app.post("/api/voices/library/add")
async def add_library_voice(body: AddVoiceBody) -> dict:
    """Add a library voice to this ElevenLabs account so the agent can use it."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"https://api.elevenlabs.io/v1/voices/add/{body.public_owner_id}/{body.voice_id}",
            headers={"xi-api-key": settings.elevenlabs_api_key},
            json={"new_name": body.name},
        )
    if resp.status_code != 200:
        detail = resp.json().get("detail", {}) if resp.headers.get("content-type", "").startswith(
            "application/json"
        ) else {}
        message = detail.get("message") if isinstance(detail, dict) else str(detail)
        raise HTTPException(502, message or f"ElevenLabs error {resp.status_code}")
    _voice_cache["at"] = 0.0  # refresh "my voices"
    return {"voice_id": resp.json().get("voice_id", body.voice_id)}


@app.get("/api/usage")
async def usage() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": settings.elevenlabs_api_key},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"ElevenLabs error {resp.status_code}")
    d = resp.json()
    return {
        "tier": d.get("tier"),
        "characters_used": d.get("character_count"),
        "characters_limit": d.get("character_limit"),
        "voice_slots": d.get("voice_limit"),
    }


# ---------- voice test: LiveKit token ----------


@app.post("/api/voice/token")
def voice_token() -> dict:
    room = f"test-{uuid.uuid4().hex[:8]}"
    token = (
        lk_api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(f"tester-{uuid.uuid4().hex[:6]}")
        .with_grants(lk_api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    return {"url": settings.livekit_url, "token": token, "room": room}


# ---------- text test: the real agent, in-process ----------


class ChatSession:
    def __init__(self, session: AgentSession, events: list[dict]) -> None:
        self.session = session
        self.events = events


_chats: dict[str, ChatSession] = {}


class ChatBody(BaseModel):
    session_id: str
    message: str


@app.post("/api/chat")
async def chat(body: ChatBody) -> dict:
    chat_session = _chats.get(body.session_id)
    if chat_session is None:
        config, knowledge = load_clinic(CLINIC_DIR)  # fresh config for every new chat
        events: list[dict] = []
        notifier = JsonlNotifier(Path(settings.handoff_path))
        agent = ClinicAgent(
            config=config,
            knowledge=knowledge,
            store=_store(config),
            notifier=notifier,
            on_event=events.append,
        )
        session = AgentSession(llm=build_llm(settings, config.agent))
        await session.start(agent)
        chat_session = _chats[body.session_id] = ChatSession(session, events)

    chat_session.events.clear()
    started = time.perf_counter()
    result = await chat_session.session.run(user_input=body.message)
    elapsed = time.perf_counter() - started
    replies = [
        e.item.text_content
        for e in result.events
        if e.item.type == "message" and e.item.role == "assistant" and e.item.text_content
    ]
    return {"replies": replies, "tools": list(chat_session.events), "seconds": round(elapsed, 2)}


@app.delete("/api/chat/{session_id}")
async def reset_chat(session_id: str) -> dict:
    chat_session = _chats.pop(session_id, None)
    if chat_session:
        await chat_session.session.aclose()
    return {"ok": True}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
