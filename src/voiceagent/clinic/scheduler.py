import uuid
from datetime import date, datetime, timedelta
from typing import Protocol

from voiceagent.clinic.models import Appointment, ClinicConfig


class SlotUnavailableError(Exception):
    pass


class AppointmentStore(Protocol):
    def free_slots(self, day: date, department: str) -> list[datetime]: ...

    def book(
        self, *, patient_name: str, patient_phone: str, department: str, start: datetime
    ) -> Appointment: ...


class InMemoryAppointmentStore:
    """Demo store. Replaced by Postgres in a later phase behind the same protocol."""

    def __init__(self, config: ClinicConfig, now: datetime) -> None:
        self._config = config
        self._now = now
        self._booked: dict[tuple[str, datetime], Appointment] = {}

    def _all_slots(self, day: date) -> list[datetime]:
        cfg = self._config
        if day.weekday() not in cfg.open_days:
            return []
        slots = []
        cur = datetime.combine(day, cfg.open_time, tzinfo=self._now.tzinfo)
        end = datetime.combine(day, cfg.close_time, tzinfo=self._now.tzinfo)
        while cur < end:
            if cur > self._now:
                slots.append(cur)
            cur += timedelta(minutes=cfg.slot_minutes)
        return slots

    def free_slots(self, day: date, department: str) -> list[datetime]:
        return [s for s in self._all_slots(day) if (department, s) not in self._booked]

    def book(
        self, *, patient_name: str, patient_phone: str, department: str, start: datetime
    ) -> Appointment:
        if start not in self.free_slots(start.date(), department):
            raise SlotUnavailableError(start.isoformat())
        appt = Appointment(
            id=uuid.uuid4().hex[:8],
            tenant_id=self._config.tenant_id,
            patient_name=patient_name,
            patient_phone=patient_phone,
            department=department,
            start=start,
            created_at=self._now,
        )
        self._booked[(department, start)] = appt
        return appt
