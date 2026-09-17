import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models.chat_session import ChatSession
from backend.database.models.rag_request import RagRequest
from backend.database.models.user import User


router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("/{request_id}")
def get_request(
    request_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    request = session.get(RagRequest, request_id)
    chat = session.get(ChatSession, request.session_id) if request else None
    if request is None or chat is None or chat.user_id != user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy request")
    return {
        "id": str(request.id),
        "status": request.status,
        "current_stage": request.current_stage,
        "final_answer": request.final_answer,
        "error": request.error,
    }
