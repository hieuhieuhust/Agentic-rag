import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base
from backend.database.models.mixins import CreatedAtMixin, IdMixin


class RagRequest(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "rag_requests"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chat_sessions.id"), index=True
    )
    user_message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("messages.id"), unique=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    current_stage: Mapped[str] = mapped_column(String(64), default="intent")
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    session = relationship("ChatSession", back_populates="rag_requests")
    user_message = relationship("Message", back_populates="rag_request")
    subtasks = relationship("RagSubtask", back_populates="rag_request")
