from rag.stages.base import ModelStage


class QueryRewriter(ModelStage):
    def rewrite(self, query: str, history: str = "") -> str:
        prompt = (
            f"Lịch sử: {history}\nCâu hỏi gốc: {query}\n"
            "Viết lại thành một truy vấn tìm kiếm rõ nghĩa. Chỉ trả về truy vấn."
        )
        return self.model.generate(prompt).strip()
