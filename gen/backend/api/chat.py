import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models.chat_session import ChatSession
from backend.database.models.message import Message
from backend.database.models.processing_job import ProcessingJob
from backend.database.models.rag_request import RagRequest
from backend.database.models.user import User
from backend.services.storage_service import StorageService
from config.constants import JobType, Status


router = APIRouter(prefix="/chat", tags=["chat"])

MAX_CHAT_IMAGE_BYTES = 10 * 1024 * 1024
CHAT_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class SessionCreate(BaseModel):
    document_id: uuid.UUID | None = None
    title: str = Field(default="Cuộc trò chuyện mới", max_length=255)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    image_url: str | None = None
    use_rag: bool = True


def valid_image_signature(content_type: str, data: bytes) -> bool:
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


@router.post("/images", status_code=201)
def upload_chat_image(
    file: UploadFile = File(),
    user: User = Depends(get_current_user),
):
    content_type = file.content_type or ""
    extension = CHAT_IMAGE_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=400, detail="Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP"
        )
    data = file.file.read(MAX_CHAT_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="File ảnh trống")
    if len(data) > MAX_CHAT_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Ảnh không được vượt quá 10 MB")
    if not valid_image_signature(content_type, data):
        raise HTTPException(status_code=400, detail="Nội dung file ảnh không hợp lệ")

    image_id = uuid.uuid4()
    image_url = StorageService().upload_chat_image(
        user.id,
        image_id,
        content_type,
        extension,
        data,
    )
    return {"id": str(image_id), "image_url": image_url}


@router.post("/sessions", status_code=201)
def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    chat = ChatSession(
        user_id=user.id, document_id=body.document_id, title=body.title
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return {"id": str(chat.id), "title": chat.title}


@router.get("/sessions")
def list_sessions(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    chats = session.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc())
    ).all()
    return [
        {"id": str(chat.id), "title": chat.title, "document_id": chat.document_id}
        for chat in chats
    ]


def owned_chat(session: Session, user: User, session_id: uuid.UUID) -> ChatSession:
    chat = session.get(ChatSession, session_id)
    if chat is None or chat.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên chat")
    return chat


@router.get("/sessions/{session_id}/messages")
def list_messages(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    owned_chat(session, user, session_id)
    messages = session.scalars(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    ).all()
    return [
        {
            "id": str(message.id),
            "role": message.role,
            "content": message.content,
            "image_url": message.image_url,
            "created_at": message.created_at,
        }
        for message in messages
    ]


@router.post("/sessions/{session_id}/messages", status_code=202)
def send_message(
    session_id: uuid.UUID,
    body: MessageCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    chat = owned_chat(session, user, session_id)
    message = Message(
        session_id=chat.id,
        role="user",
        content=body.content,
        image_url=body.image_url,
    )
    session.add(message)
    session.flush()

    request = RagRequest(
        session_id=chat.id,
        user_message_id=message.id,
        status=Status.PENDING,
        current_stage="intent",
    )
    session.add(request)
    session.flush()

    job = ProcessingJob(
        user_id=user.id,
        document_id=chat.document_id,
        rag_request_id=request.id,
        job_type=JobType.RAG,
        status=Status.PENDING,
        input_payload={
            "query": body.content,
            "image_url": body.image_url,
            "use_rag": body.use_rag,
        },
    )
    session.add(job)
    session.commit()
    return {
        "message_id": str(message.id),
        "request_id": str(request.id),
        "status": request.status,
    }
