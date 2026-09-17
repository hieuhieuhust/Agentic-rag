from rag.tools.base import RagTool
from rag.tools.search_code import SearchCodeTool
from rag.tools.search_formula import SearchFormulaTool
from rag.tools.search_headings import SearchHeadingsTool
from rag.tools.search_image import SearchImageTool
from rag.tools.search_table import SearchTableTool
from rag.tools.search_text import SearchTextTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RagTool] = {}

    def register(self, tool: RagTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool đã tồn tại: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> RagTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Không tìm thấy tool: {name}") from exc

    def schemas(self) -> list[dict]:
        return [tool.function_schema() for tool in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)


default_registry = ToolRegistry()
for tool_class in (
    SearchTextTool,
    SearchImageTool,
    SearchTableTool,
    SearchCodeTool,
    SearchFormulaTool,
    SearchHeadingsTool,
):
    default_registry.register(tool_class())
