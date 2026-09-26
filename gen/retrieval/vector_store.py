import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from config.constants import BGE_DIMENSION, SIGLIP_DIMENSION, ChunkCollection


class VectorStore:
    def __init__(self, client: QdrantClient):
        self.client = client

    def init_collections(self) -> None:
        single = (
            ChunkCollection.TEXT,
            ChunkCollection.FORMULA,
            ChunkCollection.CODE,
            ChunkCollection.HEADINGS,
        )
        for name in single:
            if not self.client.collection_exists(name):
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=BGE_DIMENSION, distance=Distance.COSINE
                    ),
                )
        if not self.client.collection_exists(ChunkCollection.IMAGE):
            self.client.create_collection(
                collection_name=ChunkCollection.IMAGE,
                vectors_config={
                    "embedding_caption": VectorParams(
                        size=BGE_DIMENSION, distance=Distance.COSINE
                    ),
                    "embedding_image": VectorParams(
                        size=SIGLIP_DIMENSION, distance=Distance.COSINE
                    ),
                },
            )
        if not self.client.collection_exists(ChunkCollection.TABLE):
            self.client.create_collection(
                collection_name=ChunkCollection.TABLE,
                vectors_config={
                    "embedding_caption": VectorParams(
                        size=BGE_DIMENSION, distance=Distance.COSINE
                    ),
                    "embedding_content": VectorParams(
                        size=BGE_DIMENSION, distance=Distance.COSINE
                    ),
                },
            )

    def upsert(self, collection: str, chunk: dict[str, Any]) -> None:
        payload = chunk.copy()
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, payload["chunk_id"]))
        if collection == ChunkCollection.IMAGE:
            vector = {"embedding_caption": payload.pop("embedding_caption")}
            image_vector = payload.pop("embedding_image", None)
            if image_vector is not None:
                vector["embedding_image"] = image_vector
        elif collection == ChunkCollection.TABLE:
            vector = {
                "embedding_caption": payload.pop("embedding_caption"),
                "embedding_content": payload.pop("embedding_content"),
            }
        else:
            vector = payload.pop("embedding")
        self.client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    @staticmethod
    def _filter(
        user_id: str,
        document_id: str | None = None,
        page_filter: int | None = None,
    ) -> Filter:
        conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=user_id))
        ]
        if document_id:
            conditions.append(
                FieldCondition(
                    key="document_id", match=MatchValue(value=document_id)
                )
            )
        if page_filter is not None:
            conditions.append(
                FieldCondition(
                    key="page_number", match=MatchValue(value=int(page_filter))
                )
            )
        return Filter(must=conditions)

    def search(
        self,
        collection: str,
        vector: list[float],
        *,
        user_id: str,
        document_id: str | None = None,
        page_filter: int | None = None,
        vector_name: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        points = self.client.query_points(
            collection_name=collection,
            query=vector,
            using=vector_name,
            query_filter=self._filter(user_id, document_id, page_filter),
            limit=limit,
        ).points
        return [
            {"do_chinh_xac": point.score, "du_lieu": point.payload}
            for point in points
        ]

    def fetch_all(
        self,
        collection: str,
        *,
        user_id: str,
        document_id: str | None = None,
        page_filter: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        query_filter = self._filter(user_id, document_id, page_filter)
        count = self.client.count(
            collection_name=collection, count_filter=query_filter, exact=True
        ).count
        points, _ = self.client.scroll(
            collection_name=collection,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return {
            "count": count,
            "items": [
                {"do_chinh_xac": 1.0, "du_lieu": point.payload}
                for point in points
            ],
        }
