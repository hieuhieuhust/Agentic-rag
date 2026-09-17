import json
from typing import Any

from openai import OpenAI


class OpenAIModel:
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def generate(
        self,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
        images: list[str] | None = None,
    ) -> str:
        content: str | list[dict[str, Any]] = prompt
        if images:
            content = [{"type": "text", "text": prompt}]
            content.extend(
                {"type": "image_url", "image_url": {"url": image}}
                for image in images
            )
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
        }
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "stage_result",
                    "strict": True,
                    "schema": json_schema,
                },
            }
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or json.dumps({})
