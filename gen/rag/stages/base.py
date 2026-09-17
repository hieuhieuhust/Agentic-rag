from pathlib import Path
from typing import Any

import yaml

from models.base import ModelClient


class ModelStage:
    def __init__(self, model: ModelClient, prompt_path: str | None = None):
        self.model = model
        self.prompt_path = Path(prompt_path) if prompt_path else None

    def load_prompt(self) -> str:
        if self.prompt_path is None:
            return ""
        data: dict[str, Any] = yaml.safe_load(
            self.prompt_path.read_text(encoding="utf-8")
        )
        return data["prompt"]
