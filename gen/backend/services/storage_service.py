import uuid

from config.settings import get_settings
from infrastructure.supabase_client import get_supabase_client


class StorageService:
    def upload_document(
        self, user_id: uuid.UUID, document_id: uuid.UUID, file_name: str, data: bytes
    ) -> str:
        settings = get_settings()
        client = get_supabase_client()
        safe_name = file_name.replace("\\", "_").replace("/", "_")
        path = f"documents/{user_id}/{document_id}/{safe_name}"
        client.storage.from_(settings.supabase_bucket).upload(
            path=path,
            file=data,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        return client.storage.from_(settings.supabase_bucket).get_public_url(path)
