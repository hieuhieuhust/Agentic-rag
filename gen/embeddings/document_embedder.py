from collections.abc import Callable

from config.constants import SIGLIP_DIMENSION
from embeddings.bge_embedder import BgeEmbedder
from embeddings.siglip_embedder import SiglipEmbedder


ProgressCallback = Callable[[int, str], None]


class DocumentEmbedder:
    def __init__(self, bge: BgeEmbedder, siglip: SiglipEmbedder):
        self.bge = bge
        self.siglip = siglip

    def embed(
        self, chunks: dict[str, list[dict]], progress: ProgressCallback | None = None
    ) -> dict[str, list[dict]]:
        notify = progress or (lambda _value, _message: None)

        notify(10, "Đang nhúng văn bản")
        for chunk in chunks.get("text_chunks", []):
            text = f"Thuộc phần: {chunk.get('heading_path', '')} \n {chunk.get('content', '')}"
            chunk["embedding"] = self.bge.encode(text)

        notify(30, "Đang nhúng bảng")
        for chunk in chunks.get("table_chunks", []):
            caption = f"Thuộc phần: {chunk.get('heading_path', '')} \n Bảng: {chunk.get('caption', '')}"
            content = f"Nội dung bảng: {chunk.get('table_horizontal_text', '')}"
            chunk["embedding_caption"] = self.bge.encode(caption)
            chunk["embedding_content"] = self.bge.encode(content)

        notify(45, "Đang nhúng công thức")
        for chunk in chunks.get("formula_chunks", []):
            formula = chunk.get("content") or chunk.get("latex", "")
            text = f"Thuộc phần: {chunk.get('heading_path', '')} \n Công thức: {formula}"
            chunk["embedding"] = self.bge.encode(text)

        notify(60, "Đang nhúng code")
        for chunk in chunks.get("code_chunks", []):
            code = chunk.get("content") or chunk.get("code_raw", "")
            text = f"Thuộc phần: {chunk.get('heading_path', '')} \n Code: {code}"
            chunk["embedding"] = self.bge.encode(text)

        notify(70, "Đang nhúng ảnh")
        embedded_images = 0
        skipped_images = 0
        for chunk in chunks.get("image_chunks", []):
            text = (
                f"Thuộc phần: {chunk.get('heading_path', '')} \n "
                f"Ảnh: {chunk.get('caption', '')} \n "
                f"Ngữ cảnh trước: {chunk.get('prev_text_snippet', '')} \n "
                f"Ngữ cảnh sau: {chunk.get('next_text_snippet', '')}"
            )
            chunk["embedding_caption"] = self.bge.encode(text)
            image_ref = chunk.get("image_ref", "")
            if not image_ref.startswith(("http://", "https://")):
                chunk["embedding_image_status"] = "missing_image_url"
                skipped_images += 1
                continue
            try:
                image_vector = self.siglip.encode_url(image_ref)
                if len(image_vector) != SIGLIP_DIMENSION or not any(image_vector):
                    raise ValueError("Vector SigLIP không hợp lệ")
                chunk["embedding_image"] = image_vector
                chunk["embedding_image_status"] = "ready"
                embedded_images += 1
            except Exception:
                chunk["embedding_image_status"] = "failed"
                skipped_images += 1

        notify(
            80,
            f"Đã nhúng {embedded_images} ảnh; bỏ qua SigLIP cho {skipped_images} ảnh",
        )

        notify(90, "Đang nhúng cấu trúc heading")
        for chunk in chunks.get("intro_chunks", []):
            chunk["embedding"] = self.bge.encode(chunk.get("content", ""))
        return chunks
