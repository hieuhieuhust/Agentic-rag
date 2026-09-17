import json

from typing import Any

from rag.stages.base import ModelStage


class SufficiencyChecker(ModelStage):
    schema = {
        "type": "object",
        "properties": {
            "sufficient": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["sufficient", "reason"],
        "additionalProperties": False,
    }

    def check(self, query: str, results: list[dict[str, Any]]) -> dict:
        prompt = (
            f"Câu hỏi: {query}\n"
            f"Dữ liệu: {json.dumps(results, ensure_ascii=False)}\n"
            "Dữ liệu đã đủ để trả lời chính xác chưa?"
        )
        return json.loads(self.model.generate(prompt, json_schema=self.schema))
