from datetime import date, datetime, time

from pydantic import BaseModel, Field


class AgentSettings(BaseModel):
    """Per-clinic agent behaviour. Empty values fall back to the global defaults in .env."""

    llm_model: str = ""
    tts_provider: str = ""  # "elevenlabs" | "openai"; empty = global default
    tts_model: str = ""
    tts_voice_id: str = ""  # ElevenLabs voice id, or an OpenAI voice name such as "marin"
    tts_instructions: str = ""  # OpenAI only: steers accent, tone and pace
    greeting: str = ""
    style_guide: str = ""  # empty = built-in default (see agent/prompts.py)
    extra_instructions: str = ""


class ClinicConfig(BaseModel):
    tenant_id: str
    name: str
    agent_name: str = "Elif"
    timezone: str = "Europe/Istanbul"
    address: str = ""
    phone_for_staff: str = ""
    open_days: list[int] = Field(default=[0, 1, 2, 3, 4], description="Mon=0 ... Sun=6")
    open_time: time = time(9, 0)
    close_time: time = time(17, 0)
    slot_minutes: int = 30
    departments: list[str] = []
    agent: AgentSettings = AgentSettings()


class Appointment(BaseModel):
    id: str
    tenant_id: str
    patient_name: str
    patient_phone: str
    department: str
    start: datetime
    created_at: datetime
    status: str = "confirmed"  # confirmed | cancelled


class StaffMessage(BaseModel):
    """Handoff to a human: what the caller wanted and what was left unresolved."""

    tenant_id: str
    caller_name: str = ""
    caller_phone: str
    summary: str
    unresolved: str
    urgent: bool = False
    created_at: datetime


class AvailabilityQuery(BaseModel):
    day: date
    department: str = ""
