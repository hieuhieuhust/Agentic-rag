from typing import Any

from config.constants import ChunkCollection
from rag.tools.base import RagTool, common_search_schema


class SearchHeadingsTool(RagTool):
    name = "search_headings"
    description = "Tìm mục lục, chương, mục và cấu trúc heading."
    target_collection = ChunkCollection.HEADINGS

    def parameters_schema(self) -> dict[str, Any]:
        return common_search_schema()
