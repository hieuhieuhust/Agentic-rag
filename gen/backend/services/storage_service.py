import uuid

from config.settings import get_settings
from infrastructure.supabase_client import get_supabase_client


def document_storage_path(user_id: uuid.UUID, document_id: uuid.UUID) -> str:
    """Use IDs for object keys; keep the original filename only in PostgreSQL."""
    return f"documents/{user_id}/{document_id}/source.pdf"


def chat_image_storage_path(
    user_id: uuid.UUID, image_id: uuid.UUID, extension: str
) -> str:
    """Keep chat-image object keys ASCII-only and scoped to one user."""
    safe_extension = extension.lower().lstrip(".")
    return f"chat-images/{user_id}/{image_id}/source.{safe_extension}"


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

    def upload_chat_image(
        self,
        user_id: uuid.UUID,
        image_id: uuid.UUID,
        content_type: str,
        extension: str,
        data: bytes,
    ) -> str:
        settings = get_settings()
        client = get_supabase_client()
        path = chat_image_storage_path(user_id, image_id, extension)
        client.storage.from_(settings.supabase_bucket).upload(
            path=path,
            file=data,
            file_options={"content-type": content_type, "upsert": "false"},
        )
        return client.storage.from_(settings.supabase_bucket).get_public_url(path)
