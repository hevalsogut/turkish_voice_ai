from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from voiceagent.clinic.models import ClinicConfig
from voiceagent.clinic.scheduler import InMemoryAppointmentStore, SlotUnavailableError

TZ = ZoneInfo("Europe/Istanbul")
CFG = ClinicConfig(tenant_id="t1", name="Test", departments=["Dahiliye"])
MONDAY = date(2026, 10, 19)
NOW = datetime(2026, 10, 17, 14, 0, tzinfo=TZ)  # a Saturday


def make_store():
    return InMemoryAppointmentStore(CFG, NOW)


def test_closed_on_weekend():
    assert make_store().free_slots(date(2026, 10, 18), "Dahiliye") == []


def test_open_day_has_expected_slots():
    slots = make_store().free_slots(MONDAY, "Dahiliye")
    assert len(slots) == 16  # 09:00-17:00 in 30 min steps
    assert slots[0].hour == 9 and slots[-1].hour == 16 and slots[-1].minute == 30


def test_past_slots_are_not_offered():
    late = InMemoryAppointmentStore(CFG, datetime(2026, 10, 19, 12, 0, tzinfo=TZ))
    assert late.free_slots(MONDAY, "Dahiliye")[0].hour == 12


def test_booking_removes_slot_and_blocks_double_booking():
    store = make_store()
    start = datetime(2026, 10, 19, 10, 0, tzinfo=TZ)
    store.book(patient_name="Ayşe", patient_phone="05320000000", department="Dahiliye", start=start)
    assert start not in store.free_slots(MONDAY, "Dahiliye")
    with pytest.raises(SlotUnavailableError):
        store.book(
            patient_name="Ali", patient_phone="05330000000", department="Dahiliye", start=start
        )


def test_other_department_slot_still_free():
    store = make_store()
    start = datetime(2026, 10, 19, 10, 0, tzinfo=TZ)
    store.book(patient_name="Ayşe", patient_phone="05320000000", department="Dahiliye", start=start)
    assert start in store.free_slots(MONDAY, "Kardiyoloji")
