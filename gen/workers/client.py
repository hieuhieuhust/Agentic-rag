from __future__ import annotations

from typing import Any

import httpx

from config.settings import get_settings


class WorkerClient:
    def __init__(self, worker_id: str):
        settings = get_settings()
        self.worker_id = worker_id
        self.base_url = settings.api_base_url.rstrip("/")
        self.headers = {"X-Worker-Token": settings.worker_token}

    def poll(self, supported_types: list[str]) -> dict[str, Any] | None:
        try:
            response = httpx.post(
                f"{self.base_url}/workers/jobs/poll",
                headers=self.headers,
                json={
                    "worker_id": self.worker_id,
                    "supported_types": supported_types,
                    "lease_seconds": 900,
                },
                timeout=30,
            )
        except httpx.RequestError as exc:
            print(f"Worker poll tạm mất kết nối: {exc}")
            return None

        if response.is_server_error:
            print(
                "Worker poll nhận lỗi tạm thời "
                f"{response.status_code}; sẽ tự thử lại"
            )
            return None
        response.raise_for_status()
        return response.json()["job"]

    def start(self, job_id: str, message: str = "") -> None:
        self.progress(job_id, 0, message, action="start")

    def progress(
        self, job_id: str, value: int, message: str = "", action: str = "progress"
    ) -> None:
        response = httpx.post(
            f"{self.base_url}/workers/jobs/{job_id}/{action}",
            headers=self.headers,
            json={
                "worker_id": self.worker_id,
                "progress": value,
                "message": message,
            },
            timeout=30,
        )
        response.raise_for_status()

    def complete(self, job_id: str, output_payload: dict[str, Any]) -> None:
        response = httpx.post(
            f"{self.base_url}/workers/jobs/{job_id}/complete",
            headers=self.headers,
            json={"worker_id": self.worker_id, "output_payload": output_payload},
            timeout=30,
        )
        response.raise_for_status()

    def fail(self, job_id: str, error: str, retryable: bool = True) -> None:
        response = httpx.post(
            f"{self.base_url}/workers/jobs/{job_id}/fail",
            headers=self.headers,
            json={
                "worker_id": self.worker_id,
                "error": error,
                "retryable": retryable,
            },
            timeout=30,
        )
        response.raise_for_status()
