from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.dependencies import get_db
from backend.database.base import Base
from backend.database import models  # noqa: F401
from backend.main import app


engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def override_db():
    with TestingSession() as session:
        yield session


app.dependency_overrides[get_db] = override_db


def setup_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_register_login_and_me():
    client = TestClient(app)
    registered = client.post(
        "/auth/register",
        json={"username": "demo_user", "password": "strong-password"},
    )
    assert registered.status_code == 201

    logged_in = client.post(
        "/auth/login",
        data={"username": "demo_user", "password": "strong-password"},
    )
    assert logged_in.status_code == 200
    token = logged_in.json()["access_token"]

    profile = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert profile.status_code == 200
    assert profile.json()["username"] == "demo_user"
