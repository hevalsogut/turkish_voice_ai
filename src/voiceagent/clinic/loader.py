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
