from abc import ABC, abstractmethod
from typing import Any

from contracts.rag import RagSubtaskData


class RagTool(ABC):
    name: str
    description: str
    target_collection: str

    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        raise NotImplementedError

    def function_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema(),
            },
        }

    def build_subtask(self, arguments: dict[str, Any]) -> RagSubtaskData:
        return RagSubtaskData(
            tool_name=self.name,
            query=arguments["query"],
            target_collection=self.target_collection,
            page_filter=arguments.get("page_filter"),
            is_counting_query=arguments.get("is_counting_query", False),
            is_fetch_all_content=arguments.get("is_fetch_all_content", False),
        )


def common_search_schema(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "query": {"type": "string"},
        "page_filter": {"type": ["integer", "null"]},
        "is_counting_query": {"type": "boolean", "default": False},
        "is_fetch_all_content": {"type": "boolean", "default": False},
    }
    properties.update(extra or {})
    return {
        "type": "object",
        "properties": properties,
        "required": ["query"],
        "additionalProperties": False,
    }
