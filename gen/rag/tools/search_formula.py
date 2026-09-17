from typing import Any

from config.constants import ChunkCollection
from rag.tools.base import RagTool, common_search_schema


class SearchFormulaTool(RagTool):
    name = "search_formula"
    description = "Tìm công thức toán học hoặc vật lý trong tài liệu."
    target_collection = ChunkCollection.FORMULA

    def parameters_schema(self) -> dict[str, Any]:
        return common_search_schema()
