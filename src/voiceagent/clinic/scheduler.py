import uuid
from collections.abc import Callable
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

    def list_appointments(self, *, include_cancelled: bool = False) -> list[Appointment]: ...

    def cancel(self, appointment_id: str) -> bool: ...


def generate_slots(config: ClinicConfig, day: date, now: datetime) -> list[datetime]:
    """All bookable slot starts for a day (open hours, in the future)."""
    if day.weekday() not in config.open_days:
        return []
    slots = []
    cur = datetime.combine(day, config.open_time, tzinfo=now.tzinfo)
    end = datetime.combine(day, config.close_time, tzinfo=now.tzinfo)
    while cur < end:
        if cur > now:
            slots.append(cur)
        cur += timedelta(minutes=config.slot_minutes)
    return slots


class InMemoryAppointmentStore:
    """Used in tests. Production uses SqliteAppointmentStore behind the same protocol."""

    def __init__(self, config: ClinicConfig, now: datetime | Callable[[], datetime]) -> None:
        self._config = config
        self._clock = now if callable(now) else (lambda: now)
        self._booked: dict[tuple[str, datetime], Appointment] = {}

    def free_slots(self, day: date, department: str) -> list[datetime]:
        return [
            s
            for s in generate_slots(self._config, day, self._clock())
            if (department, s) not in self._booked
        ]

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
            created_at=self._clock(),
        )
        self._booked[(department, start)] = appt
        return appt

    def list_appointments(self, *, include_cancelled: bool = False) -> list[Appointment]:
        return sorted(self._booked.values(), key=lambda a: a.start)

    def cancel(self, appointment_id: str) -> bool:
        for key, appt in list(self._booked.items()):
            if appt.id == appointment_id:
                del self._booked[key]
                return True
        return False
