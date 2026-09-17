import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models.document import Document
from backend.database.models.processing_job import ProcessingJob
from backend.database.models.user import User
from backend.services.storage_service import StorageService
from config.constants import JobType, Status


router = APIRouter(prefix="/documents", tags=["documents"])


def serialize(document: Document) -> dict:
    return {
        "id": str(document.id),
        "file_name": document.file_name,
        "storage_url": document.storage_url,
        "status": document.status,
        "created_at": document.created_at,
    }


@router.post("", status_code=202)
def upload_document(
    file: UploadFile = File(),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file PDF")

    document = Document(user_id=user.id, file_name=file.filename or "document.pdf")
    session.add(document)
    session.flush()

    try:
        data = file.file.read()
        document.storage_url = StorageService().upload_document(
            user.id, document.id, document.file_name, data
        )
        job = ProcessingJob(
            user_id=user.id,
            document_id=document.id,
            job_type=JobType.DOCLING,
            status=Status.PENDING,
            input_payload={"pdf_url": document.storage_url},
        )
        session.add(job)
        session.commit()
        session.refresh(document)
        return serialize(document)
    except Exception:
        session.rollback()
        raise


@router.get("")
def list_documents(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    documents = session.scalars(
        select(Document)
        .where(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
    ).all()
    return [serialize(document) for document in documents]


@router.get("/{document_id}")
def get_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    document = session.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    return serialize(document)


@router.get("/{document_id}/status")
def get_document_status(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    document = session.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    return {"document_id": str(document.id), "status": document.status}
