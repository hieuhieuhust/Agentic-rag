from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    FORMULA = "formula"
    CODE = "code"
    HEADING = "heading"


class BaseChunk(BaseModel):
    """Schema chuẩn; vẫn cho phép field cũ để bảo toàn output Docling."""

    model_config = ConfigDict(extra="allow")

    chunk_id: str
    document_id: str
    page_number: int = Field(ge=1)
    heading_path: str = ""
    heading_parent: str = ""
    heading_children: list[str] = Field(default_factory=list)
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddedChunk(BaseChunk):
    embedding: list[float] | None = None
    embedding_caption: list[float] | None = None
    embedding_content: list[float] | None = None
    embedding_image: list[float] | None = None
