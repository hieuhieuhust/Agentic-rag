import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.dependencies import verify_worker_token
from backend.database.connection import get_db
from backend.database.models.mixins import utc_now
from backend.database.models.document import Document
from backend.database.models.processing_job import ProcessingJob
from backend.database.repositories.job_repository import JobRepository
from config.constants import Status
from contracts.jobs import JobClaim, JobComplete, JobFail, JobProgress


router = APIRouter(
    prefix="/workers",
    tags=["workers"],
    dependencies=[Depends(verify_worker_token)],
)


def require_owned_job(repository: JobRepository, job_id: uuid.UUID, worker_id: str):
    job = repository.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy job")
    if job.worker_id != worker_id:
        raise HTTPException(status_code=409, detail="Job thuộc worker khác")
    return job


@router.post("/jobs/poll")
def poll_job(body: JobClaim, session: Session = Depends(get_db)):
    job = JobRepository(session).claim_next(
        worker_id=body.worker_id,
        supported_types=[item.value for item in body.supported_types],
        lease_seconds=body.lease_seconds,
    )
    if job is None:
        return {"job": None}
    return {
        "job": {
            "id": str(job.id),
            "job_type": job.job_type,
            "document_id": str(job.document_id) if job.document_id else None,
            "rag_request_id": str(job.rag_request_id)
            if job.rag_request_id
            else None,
            "user_id": str(job.user_id),
            "input_payload": job.input_payload,
            "attempt_count": job.attempt_count,
            "lease_expires_at": job.lease_expires_at,
        }
    }


@router.post("/jobs/{job_id}/start")
def start_job(
    job_id: uuid.UUID,
    body: JobProgress,
    session: Session = Depends(get_db),
):
    job = require_owned_job(JobRepository(session), job_id, body.worker_id)
    job.status = Status.PROCESSING
    job.started_at = job.started_at or utc_now()
    job.progress = body.progress
    session.commit()
    return {"status": job.status}


@router.post("/jobs/{job_id}/progress")
def update_progress(
    job_id: uuid.UUID,
    body: JobProgress,
    session: Session = Depends(get_db),
):
    job = require_owned_job(JobRepository(session), job_id, body.worker_id)
    job.status = Status.PROCESSING
    job.progress = body.progress
    job.lease_expires_at = utc_now() + timedelta(seconds=900)
    session.commit()
    return {"status": job.status, "progress": job.progress}


@router.post("/jobs/{job_id}/complete")
def complete_job(
    job_id: uuid.UUID,
    body: JobComplete,
    session: Session = Depends(get_db),
):
    job = require_owned_job(JobRepository(session), job_id, body.worker_id)
    job.status = Status.DONE
    job.progress = 100
    job.output_payload = body.output_payload
    job.completed_at = utc_now()
    job.lease_expires_at = None

    next_job_type = {
        "docling": "embedding",
        "embedding": "index_qdrant",
    }.get(job.job_type)
    if next_job_type:
        session.add(
            ProcessingJob(
                user_id=job.user_id,
                document_id=job.document_id,
                rag_request_id=job.rag_request_id,
                job_type=next_job_type,
                status=Status.PENDING,
                input_payload=body.output_payload,
            )
        )
    if job.document_id:
        document = session.get(Document, job.document_id)
        if document:
            document.status = (
                "db_done" if job.job_type == "index_qdrant" else f"{job.job_type}_done"
            )
    session.commit()
    return {"status": job.status}


@router.post("/jobs/{job_id}/fail")
def fail_job(
    job_id: uuid.UUID,
    body: JobFail,
    session: Session = Depends(get_db),
):
    job = require_owned_job(JobRepository(session), job_id, body.worker_id)
    job.error = body.error
    job.worker_id = None
    job.lease_expires_at = None
    job.status = Status.PENDING if body.retryable else Status.ERROR
    session.commit()
    return {"status": job.status}
