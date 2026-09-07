from typing import Any

import httpx

from config.settings import get_settings


class ApiClient:
    def __init__(self, token: str | None = None):
        self.base_url = get_settings().api_base_url.rstrip("/") # xóa hết / vị trí cuối cùng bên phải
        self.token = token

    @property
    # giúp khi dùng hàm thì không phải thêm cái ( ) nữa
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def register(self, username: str, password: str) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/auth/register",
            json={"username": username, "password": password},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def login(self, username: str, password: str) -> str:
        response = httpx.post(
            f"{self.base_url}/auth/login",
            data={"username": username, "password": password},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def documents(self) -> list[dict]:
        response = httpx.get(
            f"{self.base_url}/documents", headers=self.headers, timeout=30
        )
        response.raise_for_status()
        return response.json()

    def upload_document(self, name: str, content_type: str, data: bytes) -> dict:
        response = httpx.post(
            f"{self.base_url}/documents",
            headers=self.headers,
            files={"file": (name, data, content_type)},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    def create_session(self, document_id: str | None) -> dict:
        response = httpx.post(
            f"{self.base_url}/chat/sessions",
            headers=self.headers,
            json={"document_id": document_id},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def messages(self, session_id: str) -> list[dict]:
        response = httpx.get(
            f"{self.base_url}/chat/sessions/{session_id}/messages",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def send_message(
        self,
        session_id: str,
        content: str,
        *,
        image_url: str | None = None,
        use_rag: bool = True,
    ) -> dict:
        response = httpx.post(
            f"{self.base_url}/chat/sessions/{session_id}/messages",
            headers=self.headers,
            json={
                "content": content,
                "image_url": image_url,
                "use_rag": use_rag,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def request_status(self, request_id: str) -> dict:
        response = httpx.get(
            f"{self.base_url}/requests/{request_id}",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
