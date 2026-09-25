# Multimodal PDF Agentic RAG

Hệ thống hỏi đáp trên tài liệu PDF đa phương thức, hỗ trợ xử lý văn bản, hình
ảnh, bảng, công thức và mã nguồn. Phiên bản đang phát triển chính nằm trong
[`gen/`](gen/); các file cũ ở thư mục gốc được giữ lại để đối chiếu trong quá
trình tái cấu trúc.

## Trạng thái hiện tại

Đã chạy được luồng xử lý tài liệu:

```text
Streamlit
  -> FastAPI
  -> PostgreSQL job queue
  -> Docling worker (Google Colab)
  -> Supabase Storage
  -> Embedding worker (Google Colab)
  -> Database worker
  -> Qdrant
```

Các phần đã có:

- đăng ký, đăng nhập và JWT;
- quản lý tài liệu theo người dùng;
- hàng đợi PostgreSQL có claim, lease, retry giới hạn và trạng thái tiến độ;
- Docling tách text, image, table, formula, code và cấu trúc heading;
- BGE-M3 và SigLIP2 tạo embedding trên Colab;
- lưu vector và metadata vào Qdrant;
- Streamlit gọi backend thông qua HTTP API;
- tool registry và các stage nền cho Agentic RAG.

Phần hỏi đáp mới **chưa hoàn thiện end-to-end**. FastAPI đã tạo được
`rag_request`, nhưng còn cần nối query embedding, truy xuất Qdrant, Agent
Harness/vòng lặp tool và bước tổng hợp câu trả lời vào RAG worker mới.

## Kiến trúc demo

| Thành phần | Nơi chạy | Vai trò |
|---|---|---|
| Streamlit | máy cá nhân | giao diện đăng nhập, tải PDF và chat |
| FastAPI | máy cá nhân | API, xác thực và điều phối job |
| PostgreSQL | máy cá nhân | user, tài liệu, hội thoại và trạng thái job |
| Qdrant | máy cá nhân | vector và metadata của chunk |
| Docling worker | Google Colab | phân tích PDF |
| Embedding worker | Google Colab | BGE-M3 và SigLIP2 |
| Supabase Storage | cloud | PDF, ảnh và JSON trung gian |
| Cloudflare Tunnel | máy cá nhân | cung cấp HTTPS để Colab gọi FastAPI |

Các worker polling FastAPI và có thể chạy liên tục để nhận nhiều job nối tiếp.
Docling và embedding không gọi trực tiếp lẫn nhau; FastAPI, PostgreSQL job queue
và URL dữ liệu trên Supabase kết nối hai bước này.

## Cấu trúc repository

```text
code/
|-- gen/                         # hệ thống mới đang phát triển
|   |-- backend/                 # FastAPI, PostgreSQL models và services
|   |-- frontend/                # Streamlit UI và HTTP client
|   |-- processing/docling/      # logic xử lý PDF
|   |-- embeddings/              # BGE-M3, SigLIP2
|   |-- retrieval/               # Qdrant và bộ lọc truy xuất
|   |-- rag/                     # tool, stage và orchestrator
|   |-- workers/                 # worker Colab và worker local
|   |-- tests/                   # kiểm thử tự động
|   `-- legacy_runtime/          # snapshot logic Python cũ
|-- collab/                      # notebook khởi chạy và bundle builder cho Colab
|-- docling.ipynb                # notebook cũ để đối chiếu
|-- bgem3_siglip2.ipynb          # notebook embedding cũ để đối chiếu
`-- app_ui.py, tab_*             # runtime cũ để đối chiếu
```

## Dữ liệu được lưu ở đâu

- PostgreSQL: tài khoản, document, chat, message, RAG request và processing job.
- Supabase Storage: PDF gốc, ảnh cắt, `raw.json.gz` và `embedded.json.gz`.
- Qdrant: các collection `text_chunks`, `image_chunks`, `table_chunks`,
  `formula_chunks`, `code_chunks` và `intro_and_heading`.

Mọi dữ liệu truy xuất phải được lọc tối thiểu theo `user_id` và `document_id`
để tránh lẫn dữ liệu giữa người dùng.

## Chạy và kiểm thử

Hướng dẫn cấu hình PostgreSQL, Supabase, Qdrant, FastAPI và Streamlit nằm tại
[`gen/README.md`](gen/README.md). Hướng dẫn tạo bundle và chạy hai worker trên
Google Colab nằm tại [`collab/README.md`](collab/README.md).

Không commit `.env`, API key, Supabase secret, dữ liệu Qdrant local hoặc bundle
ZIP sinh tự động. Hai ZIP Colab được tạo lại bằng `collab/build_bundles.py`; nếu
cần phát hành file dựng sẵn, nên đính kèm chúng vào GitHub Release.

## Kế hoạch gần nhất

1. Kiểm tra số lượng và metadata các vector đã ghi vào Qdrant.
2. Thêm job tạo embedding cho câu hỏi.
3. Kiểm thử truy xuất từng collection độc lập.
4. Hoàn thiện RAG worker và chuyển vòng lặp từ `tab_llm_worker.py` cũ.
5. Kiểm thử hỏi đáp end-to-end, sau đó kiểm thử nhiều người dùng đồng thời.

Thiết kế chi tiết và kế hoạch mở rộng Agent Harness/MCP nằm trong
[`gen/PROJECT_CONTEXT.md`](gen/PROJECT_CONTEXT.md) và
[`gen/PROJECT_CONTEXT_UPDATE.md`](gen/PROJECT_CONTEXT_UPDATE.md).
