from functools import lru_cache

from supabase import Client, create_client

from config.settings import get_settings


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("Thiếu SUPABASE_URL hoặc SUPABASE_KEY")
    return create_client(settings.supabase_url, settings.supabase_key)
