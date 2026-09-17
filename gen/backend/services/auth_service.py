import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.user import User
from config.settings import get_settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64
    )
    return "scrypt$" + base64.b64encode(salt + derived).decode("ascii")


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, payload = encoded.split("$", 1)
        if algorithm != "scrypt":
            return False
        decoded = base64.b64decode(payload)
        salt, expected = decoded[:16], decoded[16:]
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_minutes
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at},
        settings.api_secret_key,
        algorithm="HS256",
    )


def authenticate(session: Session, username: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user
