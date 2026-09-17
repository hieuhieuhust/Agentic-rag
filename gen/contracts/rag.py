from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class RagSubtaskData(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID | None = None
    query: str
    tool_name: str
    target_collection: str
    document_id: UUID | None = None
    page_filter: int | None = None
    is_counting_query: bool = False
    is_fetch_all_content: bool = False


class RagRequestState(BaseModel):
    request_id: UUID
    session_id: UUID
    original_query: str
    current_stage: str = "intent"
    subtasks: list[RagSubtaskData] = Field(default_factory=list)
    gathered_results: list[dict[str, Any]] = Field(default_factory=list)
    loop_count: int = 0
