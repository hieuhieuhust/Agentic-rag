import uuid
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.database.models.mixins import utc_now
from backend.database.models.processing_job import ProcessingJob
from config.constants import Status


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def claim_next(
        self,
        worker_id: str,
        supported_types: list[str],
        lease_seconds: int,
    ) -> ProcessingJob | None:
        now = utc_now()
        statement = (
            select(ProcessingJob)
            .where(
                ProcessingJob.job_type.in_(supported_types),
                or_(
                    ProcessingJob.status == Status.PENDING,
                    (
                        (ProcessingJob.status == Status.CLAIMED)
                        & (ProcessingJob.lease_expires_at < now)
                    ),
                ),
            )
            .order_by(ProcessingJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = self.session.scalar(statement)
        if job is None:
            return None

        job.status = Status.CLAIMED
        job.worker_id = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.attempt_count += 1
        self.session.commit()
        self.session.refresh(job)
        return job

    def get(self, job_id: uuid.UUID) -> ProcessingJob | None:
        return self.session.get(ProcessingJob, job_id)
