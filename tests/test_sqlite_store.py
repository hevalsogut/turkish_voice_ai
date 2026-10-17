from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from voiceagent.clinic.models import ClinicConfig
from voiceagent.clinic.scheduler import SlotUnavailableError
from voiceagent.clinic.sqlite_store import SqliteAppointmentStore

TZ = ZoneInfo("Europe/Istanbul")
CFG = ClinicConfig(tenant_id="t1", name="Test", departments=["Dahiliye"])
NOW = datetime(2026, 10, 17, 14, 0, tzinfo=TZ)
START = datetime(2026, 10, 19, 10, 0, tzinfo=TZ)


def make(tmp_path):
    return SqliteAppointmentStore(CFG, tmp_path / "db.sqlite", lambda: NOW)


def book(store, name="Ayşe"):
    return store.book(
        patient_name=name, patient_phone="05320000000", department="Dahiliye", start=START
    )


def test_persists_across_instances(tmp_path):
    book(make(tmp_path))
    assert len(make(tmp_path).list_appointments()) == 1  # a second process sees it


def test_booked_slot_not_free_and_double_booking_blocked(tmp_path):
    store = make(tmp_path)
    book(store)
    assert START not in store.free_slots(date(2026, 10, 19), "Dahiliye")
    with pytest.raises(SlotUnavailableError):
        book(store, "Ali")


def test_cancel_frees_slot(tmp_path):
    store = make(tmp_path)
    appt = book(store)
    assert store.cancel(appt.id) is True
    assert store.cancel(appt.id) is False
    assert START in store.free_slots(date(2026, 10, 19), "Dahiliye")
    assert store.list_appointments() == []
    assert len(store.list_appointments(include_cancelled=True)) == 1
