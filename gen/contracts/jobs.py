from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from config.constants import JobType


class JobCreate(BaseModel):
    job_type: JobType
    document_id: UUID | None = None
    rag_request_id: UUID | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)


class JobClaim(BaseModel):
    worker_id: str
    supported_types: list[JobType]
    lease_seconds: int = Field(default=300, ge=30, le=3600)


class JobProgress(BaseModel):
    worker_id: str
    progress: int = Field(ge=0, le=100)
    message: str | None = None


class JobComplete(BaseModel):
    worker_id: str
    output_payload: dict[str, Any] = Field(default_factory=dict)


class JobFail(BaseModel):
    worker_id: str
    error: str
    retryable: bool = True
