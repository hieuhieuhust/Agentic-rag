import json

from contracts.rag import RagSubtaskData
from models.base import ModelClient
from rag.tools.registry import ToolRegistry


class ToolSelector:
    def __init__(self, model: ModelClient, registry: ToolRegistry):
        self.model = model
        self.registry = registry

    def select(self, query: str) -> list[RagSubtaskData]:
        tool_names = self.registry.names()
        schema = {
            "type": "object",
            "properties": {
                "calls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool_name": {"type": "string", "enum": tool_names},
                            "arguments": {"type": "object"},
                        },
                        "required": ["tool_name", "arguments"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["calls"],
            "additionalProperties": False,
        }
        prompt = (
            "Chọn một hoặc nhiều tool phù hợp cho truy vấn. "
            f"Tool khả dụng: {json.dumps(self.registry.schemas(), ensure_ascii=False)}. "
            f"Truy vấn: {query}"
        )
        result = json.loads(self.model.generate(prompt, json_schema=schema))
        return [
            self.registry.get(item["tool_name"]).build_subtask(item["arguments"])
            for item in result["calls"]
        ]
