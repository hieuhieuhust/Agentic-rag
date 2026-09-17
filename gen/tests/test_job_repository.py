from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models.processing_job import ProcessingJob
from backend.database.models.user import User
from backend.database.repositories.job_repository import JobRepository
from backend.services.auth_service import hash_password
from config.constants import JobType, Status


def test_worker_claims_a_job_once():
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        user = User(username="worker_test", password_hash=hash_password("password"))
        session.add(user)
        session.flush()
        job = ProcessingJob(
            user_id=user.id,
            job_type=JobType.DOCLING,
            status=Status.PENDING,
            input_payload={"pdf_url": "https://example.test/document.pdf"},
        )
        session.add(job)
        session.commit()

        claimed = JobRepository(session).claim_next(
            "worker-1", [JobType.DOCLING], lease_seconds=300
        )
        assert claimed is not None
        assert claimed.worker_id == "worker-1"
        assert claimed.status == Status.CLAIMED

        second = JobRepository(session).claim_next(
            "worker-2", [JobType.DOCLING], lease_seconds=300
        )
        assert second is None
