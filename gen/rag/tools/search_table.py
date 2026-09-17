from typing import Any

from config.constants import ChunkCollection
from rag.tools.base import RagTool, common_search_schema


class SearchTableTool(RagTool):
    name = "search_table"
    description = "Tìm bảng và số liệu trong tài liệu."
    target_collection = ChunkCollection.TABLE

    def parameters_schema(self) -> dict[str, Any]:
        return common_search_schema(
            {
                "table_query_type": {
                    "type": "string",
                    "enum": ["semantic", "content"],
                    "default": "semantic",
                }
            }
        )
