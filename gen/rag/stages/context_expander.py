from contracts.rag import RagSubtaskData


class ContextExpander:
    def build_text_queries(
        self, selected_multimodal: list[dict], document_id=None
    ) -> list[RagSubtaskData]:
        subtasks: list[RagSubtaskData] = []
        for item in selected_multimodal:
            payload = item.get("du_lieu", {})
            query = " ".join(
                value
                for value in (
                    payload.get("heading_path", ""),
                    payload.get("caption", ""),
                    payload.get("prev_text_snippet", ""),
                    payload.get("next_text_snippet", ""),
                )
                if value
            )
            if query:
                subtasks.append(
                    RagSubtaskData(
                        query=query,
                        tool_name="search_text",
                        target_collection="text_chunks",
                        document_id=document_id,
                    )
                )
        return subtasks
