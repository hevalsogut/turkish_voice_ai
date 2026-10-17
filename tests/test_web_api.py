import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from voiceagent.web import app as web


@pytest.fixture
def client(tmp_path, monkeypatch):
    clinic_dir = tmp_path / "clinic"
    shutil.copytree(Path("data/clinics/demo"), clinic_dir)
    monkeypatch.setattr(web, "CLINIC_DIR", clinic_dir)
    monkeypatch.setattr(web.settings, "db_path", str(tmp_path / "app.db"))
    monkeypatch.setattr(web.settings, "handoff_path", str(tmp_path / "handoffs.jsonl"))
    return TestClient(web.app)


def test_config_roundtrip_keeps_tenant_and_saves_agent_settings(client):
    cfg = client.get("/api/config").json()
    cfg["tenant_id"] = "attacker"  # must be ignored
    cfg["agent"]["extra_instructions"] = "Fiyat söyleme."
    cfg["departments"] = ["Dahiliye"]
    saved = client.put("/api/config", json=cfg).json()
    assert saved["tenant_id"] == "demo"
    again = client.get("/api/config").json()
    assert again["agent"]["extra_instructions"] == "Fiyat söyleme."
    assert again["departments"] == ["Dahiliye"]


def test_invalid_config_is_rejected(client):
    cfg = client.get("/api/config").json()
    cfg["slot_minutes"] = "abc"
    assert client.put("/api/config", json=cfg).status_code == 422


def test_knowledge_roundtrip(client):
    assert client.put("/api/knowledge", json={"text": "# Yeni\nMerhaba"}).status_code == 200
    assert client.get("/api/knowledge").json()["text"] == "# Yeni\nMerhaba"


def test_edited_knowledge_and_instructions_reach_the_prompt(client):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from voiceagent.agent.prompts import build_system_prompt
    from voiceagent.clinic.loader import load_clinic

    client.put("/api/knowledge", json={"text": "Otopark ücretsizdir. KUTU-42"})
    cfg = client.get("/api/config").json()
    cfg["agent"]["extra_instructions"] = "ÖZEL-KURAL"
    client.put("/api/config", json=cfg)
    config, knowledge = load_clinic(web.CLINIC_DIR)
    prompt = build_system_prompt(config, knowledge, datetime.now(ZoneInfo(config.timezone)))
    assert "KUTU-42" in prompt and "ÖZEL-KURAL" in prompt


def test_appointments_empty_and_cancel_unknown(client):
    assert client.get("/api/appointments").json() == []
    assert client.post("/api/appointments/nope/cancel").status_code == 404


def test_handoffs_empty(client):
    assert client.get("/api/handoffs").json() == []
