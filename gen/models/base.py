from typing import Any, Protocol


class ModelClient(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
        images: list[str] | None = None,
    ) -> str:
        ...
