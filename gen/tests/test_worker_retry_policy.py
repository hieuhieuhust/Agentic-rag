from backend.api.workers import can_retry_job
from config.constants import MAX_JOB_ATTEMPTS


def test_retryable_job_stops_at_attempt_limit():
    assert can_retry_job(MAX_JOB_ATTEMPTS - 1, True)
    assert not can_retry_job(MAX_JOB_ATTEMPTS, True)


def test_non_retryable_job_stops_immediately():
    assert not can_retry_job(1, False)
