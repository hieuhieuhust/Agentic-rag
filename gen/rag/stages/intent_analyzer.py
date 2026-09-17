import json

from rag.stages.base import ModelStage


class IntentAnalyzer(ModelStage):
    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["chat", "rag"]},
        },
        "required": ["intent"],
        "additionalProperties": False,
    }

    def analyze(self, query: str) -> str:
        prompt = self.load_prompt().format(query=query)
        return json.loads(self.model.generate(prompt, json_schema=self.schema))["intent"]
