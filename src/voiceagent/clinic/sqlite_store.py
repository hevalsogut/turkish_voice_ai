import sqlite3
import uuid
from collections.abc import Callable
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from voiceagent.clinic.models import Appointment, ClinicConfig
from voiceagent.clinic.scheduler import SlotUnavailableError, generate_slots

_SCHEMA = """
CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    patient_name TEXT NOT NULL,
    patient_phone TEXT NOT NULL,
    department TEXT NOT NULL,
    start TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed'
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_slot
    ON appointments (tenant_id, department, start) WHERE status = 'confirmed';
"""


class SqliteAppointmentStore:
    """Shared by the voice worker and the dashboard API (separate processes)."""

    def __init__(
        self, config: ClinicConfig, db_path: Path, clock: Callable[[], datetime]
    ) -> None:
        self._config = config
        self._db_path = db_path
        self._clock = clock
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_appt(row: sqlite3.Row) -> Appointment:
        return Appointment(
            id=row["id"],
            tenant_id=row["tenant_id"],
            patient_name=row["patient_name"],
            patient_phone=row["patient_phone"],
            department=row["department"],
            start=datetime.fromisoformat(row["start"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            status=row["status"],
        )

    def free_slots(self, day: date, department: str) -> list[datetime]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT start FROM appointments "
                "WHERE tenant_id=? AND department=? AND status='confirmed' AND start LIKE ?",
                (self._config.tenant_id, department, f"{day.isoformat()}%"),
            ).fetchall()
        taken = {datetime.fromisoformat(r["start"]) for r in rows}
        return [s for s in generate_slots(self._config, day, self._clock()) if s not in taken]

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
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute(
                    "INSERT INTO appointments VALUES (?,?,?,?,?,?,?,?)",
                    (
                        appt.id, appt.tenant_id, appt.patient_name, appt.patient_phone,
                        appt.department, appt.start.isoformat(), appt.created_at.isoformat(),
                        appt.status,
                    ),
                )
        except sqlite3.IntegrityError as exc:  # lost a race with another caller
            raise SlotUnavailableError(start.isoformat()) from exc
        return appt

    def list_appointments(self, *, include_cancelled: bool = False) -> list[Appointment]:
        query = "SELECT * FROM appointments WHERE tenant_id=?"
        if not include_cancelled:
            query += " AND status='confirmed'"
        with closing(self._connect()) as conn:
            rows = conn.execute(query + " ORDER BY start", (self._config.tenant_id,)).fetchall()
        return [self._row_to_appt(r) for r in rows]

    def cancel(self, appointment_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "UPDATE appointments SET status='cancelled' WHERE id=? AND tenant_id=? "
                "AND status='confirmed'",
                (appointment_id, self._config.tenant_id),
            )
        return cur.rowcount > 0
