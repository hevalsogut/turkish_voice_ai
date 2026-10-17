import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from voiceagent.agent.prompts import build_system_prompt
from voiceagent.clinic.handoff import JsonlNotifier
from voiceagent.clinic.loader import load_clinic
from voiceagent.clinic.models import StaffMessage


def test_demo_clinic_loads_and_prompt_contains_key_facts():
    config, knowledge = load_clinic(Path("data/clinics/demo"))
    now = datetime(2026, 10, 17, 14, 0, tzinfo=ZoneInfo(config.timezone))
    prompt = build_system_prompt(config, knowledge, now)
    assert config.name in prompt
    assert "2026-10-17 Cumartesi" in prompt
    assert "Kardiyoloji" in prompt
    assert "112" in prompt


async def test_jsonl_notifier_appends(tmp_path):
    path = tmp_path / "out" / "handoffs.jsonl"
    notifier = JsonlNotifier(path)
    msg = StaffMessage(
        tenant_id="t1", caller_phone="0532", summary="s", unresolved="u",
        created_at=datetime(2026, 10, 17, tzinfo=ZoneInfo("UTC")),
    )
    await notifier.notify(msg)
    await notifier.notify(msg)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["tenant_id"] == "t1"


def test_style_guide_default_and_override():
    config, knowledge = load_clinic(Path("data/clinics/demo"))
    now = datetime(2026, 10, 17, 14, 0, tzinfo=ZoneInfo(config.timezone))
    assert "resepsiyonistsin" in build_system_prompt(config, knowledge, now)
    config.agent.style_guide = "ÖZEL ÜSLUP {agent_name}"
    prompt = build_system_prompt(config, knowledge, now)
    assert f"ÖZEL ÜSLUP {config.agent_name}" in prompt
    assert "resepsiyonistsin" not in prompt


def test_greeting_matches_time_of_day():
    from voiceagent.agent.prompts import greeting_instruction

    config, _ = load_clinic(Path("data/clinics/demo"))
    tz = ZoneInfo(config.timezone)
    assert "Günaydın" in greeting_instruction(config, datetime(2026, 10, 17, 9, tzinfo=tz))
    assert "İyi akşamlar" in greeting_instruction(config, datetime(2026, 10, 17, 20, tzinfo=tz))
