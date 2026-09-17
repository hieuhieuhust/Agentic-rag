from typing import Any

from rag.stages.base import ModelStage


class ResultFilter(ModelStage):
    def filter_by_score(
        self, results: list[dict[str, Any]], minimum_score: float = 0.0
    ) -> list[dict[str, Any]]:
        return [
            result
            for result in results
            if float(result.get("do_chinh_xac", 0.0)) >= minimum_score
        ]
