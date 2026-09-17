from typing import Any

from config.constants import ChunkCollection
from rag.tools.base import RagTool, common_search_schema


class SearchImageTool(RagTool):
    name = "search_image"
    description = "Tìm hình ảnh, sơ đồ hoặc biểu đồ trong tài liệu."
    target_collection = ChunkCollection.IMAGE

    def parameters_schema(self) -> dict[str, Any]:
        return common_search_schema(
            {"query_image_url": {"type": ["string", "null"]}}
        )
