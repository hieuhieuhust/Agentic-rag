import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base
from backend.database.models.mixins import CreatedAtMixin, IdMixin


class RagSubtask(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "rag_subtasks"

    rag_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rag_requests.id"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100))
    query: Mapped[str] = mapped_column(Text)
    target_collection: Mapped[str] = mapped_column(String(100))
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id"), nullable=True, index=True
    )
    page_filter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    rag_request = relationship("RagRequest", back_populates="subtasks")
