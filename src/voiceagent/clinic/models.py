from datetime import date, datetime, time

from pydantic import BaseModel, Field


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


class Appointment(BaseModel):
    id: str
    tenant_id: str
    patient_name: str
    patient_phone: str
    department: str
    start: datetime
    created_at: datetime


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
