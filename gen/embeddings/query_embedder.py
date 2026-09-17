from embeddings.bge_embedder import BgeEmbedder
from embeddings.siglip_embedder import SiglipEmbedder


class QueryEmbedder:
    def __init__(self, bge: BgeEmbedder, siglip: SiglipEmbedder):
        self.bge = bge
        self.siglip = siglip

    def embed(self, query: str, image_url: str | None = None) -> list[float]:
        if image_url:
            return self.siglip.encode_url(image_url)
        return self.bge.encode(query)
