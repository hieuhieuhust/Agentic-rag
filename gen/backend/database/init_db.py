from backend.database.base import Base
from backend.database.connection import engine
from backend.database import models  # noqa: F401


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()
