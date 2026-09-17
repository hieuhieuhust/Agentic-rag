from typing import Any

from config.settings import get_settings
from models.api_model import OpenAIModel
from models.base import ModelClient
from models.finetuned_model import FineTunedHttpModel


def create_model(config: dict[str, Any]) -> ModelClient:
    provider = config["provider"]
    model = config["model"]
    settings = get_settings()

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("Thiếu OPENAI_API_KEY")
        return OpenAIModel(model=model, api_key=settings.openai_api_key)

    if provider == "finetuned":
        endpoint = config.get("endpoint")
        if not endpoint:
            raise ValueError("Model fine-tuned cần endpoint")
        return FineTunedHttpModel(
            endpoint=endpoint,
            model=model,
            token=config.get("token"),
        )

    raise ValueError(f"Provider chưa được hỗ trợ: {provider}")
