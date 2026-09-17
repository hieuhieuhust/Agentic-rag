from enum import StrEnum


class ChunkCollection(StrEnum):
    TEXT = "text_chunks"
    IMAGE = "image_chunks"
    TABLE = "table_chunks"
    FORMULA = "formula_chunks"
    CODE = "code_chunks"
    HEADINGS = "intro_and_heading"


class JobType(StrEnum):
    DOCLING = "docling"
    EMBEDDING = "embedding"
    INDEX_QDRANT = "index_qdrant"
    QUERY_EMBEDDING = "query_embedding"
    RAG = "rag"
    QWEN = "qwen"


class Status(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


BGE_DIMENSION = 1024
SIGLIP_DIMENSION = 768
DEFAULT_JOB_LEASE_SECONDS = 300
