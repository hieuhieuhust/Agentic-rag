from contracts.rag import RagSubtaskData
from rag.stages.intent_analyzer import IntentAnalyzer
from rag.stages.query_decomposer import QueryDecomposer
from rag.stages.tool_selector import ToolSelector


class RagOrchestrator:
    """Điều phối stage; việc thực thi subtask được worker/database đảm nhiệm."""

    def __init__(
        self,
        intent_analyzer: IntentAnalyzer,
        query_decomposer: QueryDecomposer,
        tool_selector: ToolSelector,
    ):
        self.intent_analyzer = intent_analyzer
        self.query_decomposer = query_decomposer
        self.tool_selector = tool_selector

    def plan(
        self, query: str, history: str = ""
    ) -> tuple[str, list[RagSubtaskData]]:
        intent = self.intent_analyzer.analyze(query)
        if intent == "chat":
            return intent, []
        subqueries = self.query_decomposer.decompose(query, history)
        tasks = [
            task for subquery in subqueries for task in self.tool_selector.select(subquery)
        ]
        return intent, tasks
