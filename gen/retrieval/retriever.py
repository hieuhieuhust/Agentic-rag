from typing import Any

from retrieval.filters import select_vector_name
from retrieval.vector_store import VectorStore


class Retriever:
    def __init__(self, store: VectorStore):
        self.store = store

    def retrieve(
        self,
        *,
        collection: str,
        user_id: str,
        query_vector: list[float] | None,
        document_id: str | None = None,
        page_filter: int | None = None,
        table_query_type: str | None = None,
        fetch_all: bool = False,
    ) -> dict[str, Any]:
        if fetch_all:
            return self.store.fetch_all(
                collection,
                user_id=user_id,
                document_id=document_id,
                page_filter=page_filter,
            )
        if query_vector is None:
            raise ValueError("Vector search cần query_vector")
        results = self.store.search(
            collection,
            query_vector,
            user_id=user_id,
            document_id=document_id,
            page_filter=page_filter,
            vector_name=select_vector_name(
                collection, len(query_vector), table_query_type
            ),
        )
        return {"count": len(results), "items": results}
