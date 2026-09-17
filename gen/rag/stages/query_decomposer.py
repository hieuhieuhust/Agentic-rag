import json

from rag.stages.base import ModelStage


class QueryDecomposer(ModelStage):
    schema = {
        "type": "object",
        "properties": {
            "queries": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["queries"],
        "additionalProperties": False,
    }

    def decompose(self, query: str, history: str = "") -> list[str]:
        prompt = self.load_prompt().format(query=query, history=history)
        result = json.loads(self.model.generate(prompt, json_schema=self.schema))
        return result["queries"] or [query]
