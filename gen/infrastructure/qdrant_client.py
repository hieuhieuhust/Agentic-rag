from functools import lru_cache

from qdrant_client import QdrantClient

from config.settings import get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    if settings.qdrant_url:
        return QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    return QdrantClient(path=settings.qdrant_path)
