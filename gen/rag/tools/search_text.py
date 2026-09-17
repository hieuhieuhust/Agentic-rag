from typing import Any

from config.constants import ChunkCollection
from rag.tools.base import RagTool, common_search_schema


class SearchTextTool(RagTool):
    name = "search_text"
    description = "Tìm văn bản lý thuyết trong tài liệu."
    target_collection = ChunkCollection.TEXT

    def parameters_schema(self) -> dict[str, Any]:
        return common_search_schema()
