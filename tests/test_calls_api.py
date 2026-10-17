import json

import pytest
from fastapi.testclient import TestClient

from voiceagent.agent.recorder import CallRecorder
from voiceagent.web import app as web


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web.settings, "calls_dir", str(tmp_path))
    return TestClient(web.app)


def test_recorded_call_is_listed_and_readable(client, tmp_path):
    rec = CallRecorder(tmp_path, "room1")
    rec.add("message", role="assistant", text="Günaydın")
    rec.add("message", role="user", text="Randevu istiyorum")
    rec.add("end")
    calls = client.get("/api/calls").json()
    assert len(calls) == 1 and calls[0]["messages"] == 2 and calls[0]["ended"] is True
    assert calls[0]["preview"] == "Randevu istiyorum"
    events = client.get(f"/api/calls/{calls[0]['id']}").json()
    assert [e["kind"] for e in events] == ["message", "message", "end"]
    json.dumps(events, ensure_ascii=False)


def test_call_id_cannot_escape_directory(client, tmp_path):
    (tmp_path.parent / "secret.jsonl").write_text('{"kind":"x","t":""}\n')
    assert client.get("/api/calls/..%2Fsecret").status_code == 404
