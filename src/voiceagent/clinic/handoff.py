from pathlib import Path
from typing import Protocol

from voiceagent.clinic.models import StaffMessage


class StaffNotifier(Protocol):
    async def notify(self, message: StaffMessage) -> None: ...


class JsonlNotifier:
    """Appends handoffs to a local file. Telegram/WhatsApp/SMS notifiers share the protocol."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def notify(self, message: StaffMessage) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(message.model_dump_json() + "\n")
