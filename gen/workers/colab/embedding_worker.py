import gzip
import json
import tempfile
import time
import urllib.request
from pathlib import Path

from config.constants import JobType
from config.settings import get_settings
from embeddings.bge_embedder import BgeEmbedder
from embeddings.document_embedder import DocumentEmbedder
from embeddings.siglip_embedder import SiglipEmbedder
from infrastructure.supabase_client import get_supabase_client
from workers.client import WorkerClient


def download_json(url: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as temporary:
        path = Path(temporary.name)
    try:
        urllib.request.urlretrieve(url, path)
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    finally:
        path.unlink(missing_ok=True)


def upload_json(document_id: str, chunks: dict) -> str:
    settings = get_settings()
    supabase = get_supabase_client()
    remote_path = f"documents/{document_id}/embedded.json.gz"
    with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as temporary:
        path = Path(temporary.name)
    try:
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(chunks, stream, ensure_ascii=False)
        supabase.storage.from_(settings.supabase_bucket).upload(
            path=remote_path,
            file=str(path),
            file_options={"content-type": "application/gzip", "upsert": "true"},
        )
        return supabase.storage.from_(settings.supabase_bucket).get_public_url(
            remote_path
        )
    finally:
        path.unlink(missing_ok=True)


def start_embedding_worker(
    worker_id: str = "colab-embedding-1", poll_interval: int = 3
) -> None:
    client = WorkerClient(worker_id)
    embedder = DocumentEmbedder(BgeEmbedder(), SiglipEmbedder())
    while True:
        job = client.poll([JobType.EMBEDDING])
        if job is None:
            time.sleep(poll_interval)
            continue
        try:
            client.start(job["id"], "Đang tải raw chunks")
            chunks = download_json(job["input_payload"]["raw_json_url"])
            chunks = embedder.embed(
                chunks,
                progress=lambda value, message: client.progress(
                    job["id"], value, message
                ),
            )
            url = upload_json(job["document_id"], chunks)
            client.complete(job["id"], {"embedded_json_url": url})
        except Exception as exc:
            client.fail(job["id"], str(exc), retryable=True)


if __name__ == "__main__":
    start_embedding_worker()
