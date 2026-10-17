import json
from datetime import UTC, datetime
from pathlib import Path


class CallRecorder:
    """Appends one JSON line per event (message, tool call, latency) to a per-call file."""

    def __init__(self, directory: Path, call_id: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self.path = directory / f"{stamp}-{call_id}.jsonl"

    def add(self, kind: str, **data: object) -> None:
        line = {"t": datetime.now(UTC).isoformat(), "kind": kind, **data}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
