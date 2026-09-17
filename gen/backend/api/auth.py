from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models.user import User
from backend.services.auth_service import (
    authenticate,
    create_access_token,
    hash_password,
)


router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(id=str(user.id), username=user.username)


@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: RegisterRequest, session: Session = Depends(get_db)):
    existing = session.scalar(select(User).where(User.username == body.username))
    if existing:
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại")
    user = User(username=body.username, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse.from_user(user)


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db),
):
    user = authenticate(session, form.username, form.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return UserResponse.from_user(user)
