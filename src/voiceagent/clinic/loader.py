from pathlib import Path

import yaml

from voiceagent.clinic.models import ClinicConfig


def load_clinic(directory: Path) -> tuple[ClinicConfig, str]:
    """Return the clinic config and its knowledge-base text."""
    config = ClinicConfig.model_validate(
        yaml.safe_load((directory / "clinic.yaml").read_text(encoding="utf-8"))
    )
    knowledge = (directory / "knowledge.md").read_text(encoding="utf-8")
    return config, knowledge


def save_clinic(directory: Path, config: ClinicConfig) -> None:
    data = config.model_dump(mode="json")
    (directory / "clinic.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def save_knowledge(directory: Path, text: str) -> None:
    (directory / "knowledge.md").write_text(text, encoding="utf-8")
