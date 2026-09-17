class BgeEmbedder:
    def __init__(self, model_name: str = "BAAI/bge-m3", device: str | None = None):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device=device)

    def encode(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()
