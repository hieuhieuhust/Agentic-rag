from fastapi import FastAPI

from backend.api import auth, chat, documents, requests, workers
from config.settings import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(requests.router)
app.include_router(workers.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
