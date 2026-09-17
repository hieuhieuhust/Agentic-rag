import json
from typing import Any

from rag.stages.base import ModelStage


class AnswerGenerator(ModelStage):
    def generate(
        self, query: str, results: list[dict[str, Any]], history: str = ""
    ) -> str:
        prompt = self.load_prompt().format(
            query=query,
            history=history,
            context=json.dumps(results, ensure_ascii=False),
        )
        return self.model.generate(prompt).strip()
