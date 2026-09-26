from config.constants import SIGLIP_DIMENSION
from embeddings.document_embedder import DocumentEmbedder


class FakeBge:
    def encode(self, _text: str) -> list[float]:
        return [0.1, 0.2]


class FakeSiglip:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    def encode_url(self, _url: str) -> list[float]:
        if self.fail:
            raise RuntimeError("download failed")
        return [0.1] * SIGLIP_DIMENSION


def test_image_embedding_keeps_caption_and_valid_siglip_vector():
    chunks = {
        "image_chunks": [
            {
                "image_ref": "https://example.test/image.png",
                "caption": "Biểu đồ",
            }
        ]
    }

    result = DocumentEmbedder(FakeBge(), FakeSiglip()).embed(chunks)
    image = result["image_chunks"][0]

    assert image["embedding_caption"] == [0.1, 0.2]
    assert len(image["embedding_image"]) == SIGLIP_DIMENSION
    assert image["embedding_image_status"] == "ready"


def test_failed_siglip_does_not_store_zero_vector():
    chunks = {
        "image_chunks": [
            {
                "image_ref": "https://example.test/missing.png",
                "caption": "Biểu đồ",
            }
        ]
    }

    result = DocumentEmbedder(FakeBge(), FakeSiglip(fail=True)).embed(chunks)
    image = result["image_chunks"][0]

    assert "embedding_image" not in image
    assert image["embedding_image_status"] == "failed"


def test_missing_image_url_keeps_caption_only():
    chunks = {"image_chunks": [{"image_ref": "", "caption": "Biểu đồ"}]}

    result = DocumentEmbedder(FakeBge(), FakeSiglip()).embed(chunks)
    image = result["image_chunks"][0]

    assert image["embedding_caption"] == [0.1, 0.2]
    assert "embedding_image" not in image
    assert image["embedding_image_status"] == "missing_image_url"
