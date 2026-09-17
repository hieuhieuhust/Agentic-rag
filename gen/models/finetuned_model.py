from typing import Any

import httpx


class FineTunedHttpModel:
    """Adapter cho model fine-tuned được phục vụ qua HTTP."""

    def __init__(self, endpoint: str, model: str, token: str | None = None):
        self.endpoint = endpoint
        self.model = model
        self.token = token

    def generate(
        self,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
        images: list[str] | None = None,
    ) -> str:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = httpx.post(
            self.endpoint,
            headers=headers,
            json={
                "model": self.model,
                "prompt": prompt,
                "json_schema": json_schema,
                "images": images or [],
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["text"]
