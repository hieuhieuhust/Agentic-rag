import gzip
import json
import os
import tempfile
import time
import urllib.request
from pathlib import Path

from config.constants import JobType
from config.settings import get_settings
from infrastructure.supabase_client import get_supabase_client
from processing.docling.converter import convert_pdf
from processing.docling.pipeline import process_document
from workers.client import WorkerClient


def upload_chunks(document_id: str, chunks: dict) -> str:
    settings = get_settings()
    supabase = get_supabase_client()
    remote_path = f"documents/{document_id}/raw.json.gz"
    with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as temporary:
        temporary_path = temporary.name
    try:
        with gzip.open(temporary_path, "wt", encoding="utf-8") as stream:
            json.dump(chunks, stream, ensure_ascii=False)
        supabase.storage.from_(settings.supabase_bucket).upload(
            path=remote_path,
            file=temporary_path,
            file_options={"content-type": "application/gzip", "upsert": "true"},
        )
        return supabase.storage.from_(settings.supabase_bucket).get_public_url(
            remote_path
        )
    finally:
        Path(temporary_path).unlink(missing_ok=True)


def process_job(client: WorkerClient, job: dict) -> None:
    job_id = job["id"]
    document_id = job["document_id"]
    pdf_url = job["input_payload"]["pdf_url"]
    client.start(job_id, "Đang tải PDF")

    with tempfile.TemporaryDirectory(prefix=f"docling_{document_id}_") as temp_dir:
        pdf_path = os.path.join(temp_dir, "document.pdf")
        urllib.request.urlretrieve(pdf_url, pdf_path)
        client.progress(job_id, 15, "Docling đang phân tích PDF")

        document = convert_pdf(pdf_path)
        client.progress(job_id, 45, "Đang xử lý cấu trúc tài liệu")
        chunks, _diagnostics = process_document(
            pdf_path,
            document,
            document_id,
            supabase_client=get_supabase_client(),
            image_output_dir=os.path.join(temp_dir, "cropped_images"),
        )
        client.progress(job_id, 90, "Đang tải kết quả lên Storage")
        raw_json_url = upload_chunks(document_id, chunks)
        client.complete(
            job_id,
            {
                "raw_json_url": raw_json_url,
                "chunk_counts": {
                    name: len(items) for name, items in chunks.items()
                },
            },
        )


def start_docling_worker(
    worker_id: str = "colab-docling-1", poll_interval: int = 3
) -> None:
    client = WorkerClient(worker_id)
    while True:
        job = client.poll([JobType.DOCLING])
        if job is None:
            time.sleep(poll_interval)
            continue
        try:
            process_job(client, job)
        except Exception as exc:
            client.fail(job["id"], str(exc), retryable=True)


if __name__ == "__main__":
    start_docling_worker()
