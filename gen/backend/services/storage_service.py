import uuid

from config.settings import get_settings
from infrastructure.supabase_client import get_supabase_client


def document_storage_path(user_id: uuid.UUID, document_id: uuid.UUID) -> str:
    """Use IDs for object keys; keep the original filename only in PostgreSQL."""
    return f"documents/{user_id}/{document_id}/source.pdf"


class StorageService:
    def upload_document(
        self, user_id: uuid.UUID, document_id: uuid.UUID, file_name: str, data: bytes
    ) -> str:
        settings = get_settings()
        client = get_supabase_client()
        path = document_storage_path(user_id, document_id)
        client.storage.from_(settings.supabase_bucket).upload(
            path=path,
            file=data,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        return client.storage.from_(settings.supabase_bucket).get_public_url(path)
