# Multimodal PDF Agentic RAG — `gen`

`gen` là phiên bản đang tái cấu trúc của hệ thống hỏi đáp tài liệu PDF đa phương
thức. Mục tiêu là tách giao diện, API, dữ liệu, worker GPU và RAG thành các phần
độc lập để dễ kiểm thử, thay model và phục vụ nhiều người dùng.

> Trạng thái hiện tại: kiến trúc nền, xác thực, PostgreSQL, hàng đợi công việc,
> worker Docling/embedding/index và các module RAG đã có. Luồng Agentic RAG nhiều
> chặng của hệ thống cũ chưa được nối hoàn chỉnh end-to-end vào FastAPI.

## 1. Luồng hệ thống dự kiến

### Xử lý PDF

1. Người dùng đăng nhập và tải PDF từ Streamlit.
2. Streamlit gửi file tới FastAPI bằng HTTP.
3. FastAPI lưu file vào Supabase Storage, tạo `documents` và job `docling`
   trong PostgreSQL.
4. Docling worker trên Colab liên tục hỏi FastAPI để nhận job, tải PDF, phân
   tích và tải kết quả chunk lên Supabase.
5. Khi Docling hoàn thành, backend tạo job `embedding`.
6. Embedding worker trên Colab tạo vector BGE-M3/SigLIP2 và tải kết quả lên
   Supabase.
7. Backend tạo job `index_qdrant`; database worker tải kết quả và ghi vector
   vào Qdrant.

### Hỏi đáp

1. Streamlit gửi câu hỏi tới FastAPI.
2. FastAPI lưu message và tạo `rag_request` trong PostgreSQL.
3. RAG pipeline phân tích ý định, phân rã câu hỏi và chọn tool/collection.
4. Hệ thống tạo embedding truy vấn, tìm kiếm Qdrant, lọc kết quả, kiểm tra mức
   độ đầy đủ và có thể viết lại truy vấn trong số vòng lặp giới hạn.
5. LLM tổng hợp câu trả lời; kết quả được lưu vào PostgreSQL và trả về UI.

Bước 3–5 của luồng hỏi đáp hiện mới có các module thành phần, chưa có RAG worker
hoàn chỉnh để vận hành toàn bộ chu trình.

## 2. Cấu trúc thư mục

```text
gen/
|-- app.py                         # entrypoint Streamlit
|-- backend/
|   |-- main.py                    # entrypoint FastAPI
|   |-- api/                       # auth, documents, chat, requests, workers
|   |-- database/                  # kết nối, model và repository PostgreSQL
|   `-- services/                  # xác thực và lưu trữ
|-- frontend/                      # giao diện và HTTP client
|-- processing/docling/            # logic xử lý PDF được tách từ notebook cũ
|-- embeddings/                    # BGE-M3, SigLIP2 và embedding truy vấn
|-- retrieval/                     # Qdrant, filter và retriever
|-- rag/
|   |-- stages/                    # các bước xử lý RAG độc lập
|   |-- tools/                     # sáu tool tìm kiếm nội bộ
|   |-- prompts/                   # prompt cấu hình riêng theo từng bước
|   |-- orchestrator.py            # lập kế hoạch RAG hiện tại
|   `-- state.py                   # trạng thái request
|-- workers/
|   |-- colab/                     # Docling và embedding worker dùng GPU
|   `-- local/                     # worker ghi Qdrant
|-- notebooks/                     # notebook mỏng để khởi chạy worker trên Colab
|-- infrastructure/                # client Supabase và Qdrant
|-- models/                        # interface model API/finetuned
|-- contracts/                     # cấu trúc dữ liệu dùng chung
|-- config/                        # settings, constants và pipeline.yaml
|-- tests/                         # kiểm thử hiện có
`-- legacy_runtime/                # snapshot nguyên trạng logic Python cũ
```

## 3. Thành phần chạy ở đâu

| Thành phần | Nơi chạy trong giai đoạn demo | Vai trò |
|---|---|---|
| Streamlit | máy cá nhân | giao diện đăng nhập, tải PDF và chat |
| FastAPI | máy cá nhân | API, xác thực, phân quyền và điều phối job |
| PostgreSQL | máy cá nhân | user, document, chat, request và trạng thái job |
| Qdrant | máy cá nhân hoặc server truy cập được | lưu và tìm kiếm vector; hiện dùng local embedded |
| Docling worker | Google Colab | xử lý PDF cần GPU/RAM lớn |
| Embedding worker | Google Colab | chạy BGE-M3 và SigLIP2 |
| Database worker | máy cá nhân | ghi dữ liệu embedding vào Qdrant |
| Supabase Storage | cloud | lưu PDF, ảnh và JSON lớn |

Các worker hoạt động theo kiểu polling: chúng chạy liên tục, nhận job mới từ
FastAPI và không cần khởi động lại sau mỗi tài liệu.

## 4. Dữ liệu PostgreSQL

- `users`: tài khoản người dùng.
- `documents`: PDF thuộc từng người dùng.
- `chat_sessions`: phiên hội thoại của người dùng, có thể gắn với tài liệu.
- `messages`: message `user`, `assistant` hoặc `system` trong một phiên.
- `rag_requests`: trạng thái tổng của một lần hỏi đáp.
- `rag_subtasks`: các truy vấn con và tool được chọn.
- `processing_jobs`: job Docling, embedding và index Qdrant.

Qdrant payload phải chứa tối thiểu `user_id`, `document_id` và `chunk_id` để
lọc dữ liệu theo đúng người dùng và tài liệu.

## 5. Sáu tool RAG hiện có

- `search_text`
- `search_image`
- `search_table`
- `search_formula`
- `search_code`
- `search_headings`

Các tool dùng chung interface và được đăng ký trong `rag/tools/registry.py`, do
đó có thể bổ sung tool mới mà không đặt toàn bộ logic vào LLM worker.

## 6. Cấu hình môi trường

Thực hiện các lệnh trong thư mục `gen`.

```powershell
Copy-Item .env.example .env
```

Cần cấu hình tối thiểu:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/multimodal_rag
API_SECRET_KEY=chuoi-ngau-nhien-dai-va-bi-mat
WORKER_TOKEN=chuoi-token-rieng-cho-worker
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
SUPABASE_BUCKET=rag-data
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_PATH=../qdrant_db_local
OPENAI_API_KEY=
```

Không commit file `.env`, service-account Firebase hoặc bất kỳ API key nào.
Bucket Supabase nên để private và cấp signed URL khi triển khai thật.

## 7. Chạy phần local

Tạo môi trường ảo và cài thư viện:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Tạo database `multimodal_rag` trong PostgreSQL, sau đó tạo bảng:

```powershell
python -m backend.database.init_db
```

Khởi động FastAPI:

```powershell
uvicorn backend.main:app --reload
```

Kiểm tra API tại `http://127.0.0.1:8000/health` và tài liệu Swagger tại
`http://127.0.0.1:8000/docs`.

Mở terminal khác và khởi động Streamlit:

```powershell
streamlit run app.py
```

Khởi động worker ghi Qdrant ở một terminal riêng:

```powershell
python -m workers.local.database_worker
```

## 8. Chạy worker trên Colab

Hai notebook đã dùng để kiểm thử nằm trong thư mục `../collab`:

- `../collab/docling_worker.ipynb`
- `../collab/embedding_worker.ipynb`

Chạy `python ../collab/build_bundles.py` từ thư mục `gen` để tạo lại hai ZIP
sau khi mã nguồn thay đổi. Colab cần truy cập được FastAPI qua URL HTTPS công
khai trong thời gian demo. Notebook nhập `API_BASE_URL`, `WORKER_TOKEN` và cấu
hình Supabase lúc chạy, sau đó worker polling liên tục để nhận job.

Không commit các bundle ZIP. Xem hướng dẫn đầy đủ tại `../collab/README.md`.

## 9. Kiểm thử

```powershell
pytest tests -q
```

Kiểm thử hiện tại bao phủ bước đầu cho:

- đăng ký/đăng nhập;
- repository job queue;
- retry giới hạn và worker tiếp tục sau lỗi kết nối tạm thời;
- đường dẫn PDF an toàn khi tải lên Supabase;
- tool registry;
- việc tách logic Docling khỏi notebook;
- snapshot các file Python cũ trong `legacy_runtime`.

Các test này chưa thay thế kiểm thử end-to-end bằng PostgreSQL, Supabase,
Qdrant, Colab và PDF thật.

## 10. `legacy_runtime` dùng để làm gì?

`legacy_runtime` chứa toàn bộ logic Python của hệ thống cũ để không thất lạc
trong quá trình tái cấu trúc. Nó chỉ là nguồn đối chiếu và **không được FastAPI
hoặc worker mới gọi trực tiếp**.

Logic Docling, đặc biệt các bước sửa nhầm giữa text, code, ảnh, bảng, công thức
và heading, không được thay đổi nếu chưa có kiểm thử tương đương và sự đồng ý
rõ ràng.

## 11. Phần chưa hoàn thành

- Chưa chuyển toàn bộ vòng xử lý của `legacy_runtime/tab_llm_worker.py` vào RAG
  worker mới.
- Chưa lưu đầy đủ trạng thái vòng lặp, kết quả trung gian và chunk được chọn vào
  PostgreSQL.
- Chưa nối end-to-end: câu hỏi → embedding → tool → Qdrant → kiểm tra đủ dữ
  liệu → trả lời.
- Agent Harness và MCP mới nằm trong kế hoạch, chưa được triển khai.
- Chưa kiểm thử tải đồng thời nhiều người dùng trên hạ tầng thật.
- Chưa triển khai WebSocket; UI hiện dùng polling để lấy trạng thái.

Tài liệu chi tiết hơn nằm trong `PROJECT_CONTEXT.md` và
`PROJECT_CONTEXT_UPDATE.md`.
