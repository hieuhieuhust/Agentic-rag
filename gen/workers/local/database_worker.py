import gzip
import json
import tempfile
import time
import urllib.request
from pathlib import Path

from config.constants import ChunkCollection, JobType
from infrastructure.qdrant_client import get_qdrant_client
from retrieval.vector_store import VectorStore
from workers.client import WorkerClient


COLLECTIONS = {
    "text_chunks": ChunkCollection.TEXT,
    "image_chunks": ChunkCollection.IMAGE,
    "table_chunks": ChunkCollection.TABLE,
    "formula_chunks": ChunkCollection.FORMULA,
    "code_chunks": ChunkCollection.CODE,
    "intro_chunks": ChunkCollection.HEADINGS,
}


def download_json(url: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as temporary:
        path = Path(temporary.name)
    try:
        urllib.request.urlretrieve(url, path)
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    finally:
        path.unlink(missing_ok=True)


def index_job(store: VectorStore, job: dict) -> dict[str, int]:
    chunks = download_json(job["input_payload"]["embedded_json_url"])
    counts: dict[str, int] = {}
    for group_name, collection in COLLECTIONS.items():
        group = chunks.get(group_name, [])
        for chunk in group:
            chunk["user_id"] = job["user_id"]
            store.upsert(collection, chunk)
        counts[group_name] = len(group)
    return counts


def start_database_worker(
    worker_id: str = "local-database-1", poll_interval: int = 2
) -> None:
    client = WorkerClient(worker_id)
    store = VectorStore(get_qdrant_client())
    store.init_collections()
    while True:
        job = client.poll([JobType.INDEX_QDRANT])
        if job is None:
            time.sleep(poll_interval)
            continue
        try:
            client.start(job["id"], "Đang lưu vector vào Qdrant")
            counts = index_job(store, job)
            client.complete(job["id"], {"indexed_counts": counts})
        except Exception as exc:
            client.fail(job["id"], str(exc), retryable=True)


if __name__ == "__main__":
    start_database_worker()
