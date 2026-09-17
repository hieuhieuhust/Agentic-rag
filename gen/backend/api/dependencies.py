import uuid

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models.user import User
from config.settings import get_settings


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_db),
) -> User:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.api_secret_key, algorithms=["HS256"])
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ",
        ) from exc

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Không tìm thấy người dùng")
    return user


def verify_worker_token(x_worker_token: str = Header()) -> None:
    expected = get_settings().worker_token
    if (
        not expected
        or expected == "change-this-development-worker-token"
        or x_worker_token != expected
    ):
        raise HTTPException(status_code=401, detail="Worker token không hợp lệ")
