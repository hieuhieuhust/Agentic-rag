from typing import Any

from config.constants import ChunkCollection
from rag.tools.base import RagTool, common_search_schema


class SearchCodeTool(RagTool):
    name = "search_code"
    description = "Tìm mã nguồn trong tài liệu."
    target_collection = ChunkCollection.CODE

    def parameters_schema(self) -> dict[str, Any]:
        return common_search_schema()
