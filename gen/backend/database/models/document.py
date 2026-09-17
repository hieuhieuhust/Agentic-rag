import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base
from backend.database.models.mixins import CreatedAtMixin, IdMixin


class Document(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(255))
    storage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)

    user = relationship("User", back_populates="documents")
    chat_sessions = relationship("ChatSession", back_populates="document")
    processing_jobs = relationship("ProcessingJob", back_populates="document")
