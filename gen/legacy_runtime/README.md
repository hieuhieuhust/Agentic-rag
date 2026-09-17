# Legacy runtime snapshot

Thư mục này lưu bản sao nguyên trạng của các file Python thuộc hệ thống cũ.

Mục đích:

- bảo đảm toàn bộ logic cũ đã nằm bên trong `gen` trước khi tái cấu trúc;
- tạo nguồn đối chiếu để không làm thay đổi thuật toán Docling, embedding và RAG;
- cho phép chuyển từng hàm sang kiến trúc mới theo các commit nhỏ.

Các file trong thư mục này **không phải entrypoint của hệ thống mới** và chưa được
FastAPI hoặc worker mới import. Không sửa thuật toán trực tiếp ở đây; khi tích hợp,
hãy chuyển logic sang module đích và bổ sung kiểm thử tương đương.

Các khóa bí mật không được sao chép nguyên trạng. Hai worker Supabase đọc
`SUPABASE_URL` và `SUPABASE_KEY` từ biến môi trường; ngoài thay đổi cấu hình bắt
buộc này, kiểm thử snapshot đối chiếu toàn bộ phần logic còn lại với nguồn cũ.

## Các logic đã lưu

| Nguồn cũ | Bản sao trong thư mục này | Nhóm logic |
|---|---|---|
| `app_ui.py` | `app_ui.py` | Streamlit, upload PDF, chat và trạng thái |
| `bridge_module.py` | `bridge_module.py` | hậu xử lý Docling và đóng gói chunk |
| `tab_docling_worker.py` | `tab_docling_worker.py` | điều phối xử lý PDF cũ |
| `tab_embedding_worker.py` | `tab_embedding_worker.py` | embedding tài liệu và truy vấn |
| `database_manager.py` | `database_manager.py` | collection, ghi và tìm kiếm Qdrant |
| `tab_db_worker.py` | `tab_db_worker.py` | nhận kết quả và thao tác database |
| `tab_llm_worker.py` | `tab_llm_worker.py` | router, sáu tool schema, lọc, lặp và trả lời |
| `tab_qwen_worker.py` | `tab_qwen_worker.py` | xử lý ảnh bằng Qwen |

Hai notebook cũ không được sao chép thêm lần nữa:

- logic `docling.ipynb` đã được tách vào `gen/processing/docling/` và được đối
  chiếu bằng `tests/test_docling_extraction.py`;
- logic runtime của `bgem3_siglip2.ipynb` tương ứng với
  `tab_embedding_worker.py`, đồng thời các model được tách vào `gen/embeddings/`.
