# Bối cảnh dự án Multimodal PDF RAG

Toàn bộ mã nguồn tái cấu trúc mới nằm trong thư mục `code/gen`. Các file hệ thống cũ vẫn nằm trực tiếp trong `code` và chưa bị thay đổi.

## Trạng thái triển khai ngày 2026-09-06

Đã tạo song song với hệ thống cũ:

- Config, contracts/schema dùng chung.
- FastAPI với auth, document, chat, request và worker job endpoints.
- SQLAlchemy models cho bảy bảng PostgreSQL.
- Worker claim job có lease, retry và khóa hàng chống nhận trùng.
- Streamlit mới gọi FastAPI qua frontend/api_client.py.
- Tool registry và tám RAG stage độc lập, nhận model qua adapter/config.
- BGE, SigLIP, retrieval và Qdrant adapter mới.
- Docling được tách cơ học từ notebook thành module.
- Notebook Colab mỏng cho Docling và embedding.
- Chuỗi job tài liệu Docling -> Embedding -> Index Qdrant.
- Sáu test đang chạy thành công.

Chưa chuyển entrypoint cũ sang kiến trúc mới. app_ui.py, các tab worker và notebook cũ vẫn được giữ nguyên để đối chiếu. RAG worker mới chưa được nối end-to-end với toàn bộ logic nhiều chặng trong tab_llm_worker.py. Trước khi chuyển chính thức cần cấu hình PostgreSQL/Supabase thật và chạy PDF mẫu so sánh đầu ra.

## 1. Mục tiêu và quyết định đã chốt

Xây dựng hệ thống hỏi đáp đa phương thức trên PDF, hỗ trợ nhiều người dùng và tách riêng từng bước để dễ thay API bằng model fine-tuned, bổ sung tool, kiểm thử và mở rộng worker.

- Giữ Streamlit làm frontend.
- Dùng một FastAPI làm backend trung tâm.
- PostgreSQL và Qdrant chạy trên máy cá nhân.
- Docling, embedding và model cần GPU chạy trên Google Colab.
- Supabase Storage lưu PDF, ảnh và JSON lớn.
- Colab giao tiếp với PostgreSQL và Qdrant thông qua FastAPI, không mở trực tiếp cổng database ra Internet.

## 2. Thành phần hiện tại

- app_ui.py: giao diện Streamlit, upload PDF, gửi câu hỏi và chờ kết quả.
- docling.ipynb: khoảng 3.149 dòng code; chứa Docling, heading, mục lục, ảnh, bảng, code, context, chunk và worker.
- bgem3_siglip2.ipynb: tạo embedding tài liệu và truy vấn.
- tab_docling_worker.py: worker nhận PDF; hiện phụ thuộc các hàm đã chạy trong notebook nên chưa độc lập hoàn chỉnh.
- tab_db_worker.py: lưu và truy vấn Qdrant local.
- tab_llm_worker.py: phân tích ý định, phân rã câu hỏi, chọn tool, truy xuất nhiều chặng, lọc, đánh giá và tổng hợp đáp án.
- tab_qwen_worker.py: worker ảnh ngoài PDF; hiện mới là mock.
- database_manager.py: khởi tạo, ghi và truy vấn Qdrant.
- bridge_module.py: hậu xử lý Docling và đóng gói chunk; đang trùng logic notebook và chưa được import trực tiếp.

Sáu nhóm dữ liệu:

- text_chunks
- image_chunks
- table_chunks
- formula_chunks
- code_chunks
- intro_and_heading

## 3. Luồng hệ thống mục tiêu

Nhập tài liệu:

    Streamlit
      -> FastAPI tạo document và processing job
      -> Supabase lưu PDF
      -> Docling worker trên Colab tạo raw JSON
      -> Embedding worker trên Colab tạo vector
      -> Database worker lưu vào Qdrant
      -> PostgreSQL cập nhật trạng thái

Truy vấn:

    Streamlit
      -> FastAPI tạo message và RAG request
      -> RAG orchestrator phân tích và tạo subtask
      -> Embedding worker tạo vector câu hỏi hoặc ảnh
      -> Database worker truy vấn Qdrant
      -> RAG lọc, làm giàu, tự kiểm tra và tổng hợp
      -> PostgreSQL lưu câu trả lời
      -> Streamlit lấy và hiển thị kết quả

## 4. Cấu trúc thư mục mục tiêu

    project/
    +-- app.py
    +-- requirements.txt
    +-- .env.example
    |
    +-- config/
    |   +-- settings.py
    |   +-- constants.py
    |   +-- pipeline.yaml
    |
    +-- frontend/
    |   +-- auth_ui.py
    |   +-- document_ui.py
    |   +-- chat_ui.py
    |   +-- api_client.py
    |
    +-- backend/
    |   +-- main.py
    |   +-- api/
    |   |   +-- auth.py
    |   |   +-- documents.py
    |   |   +-- chat.py
    |   |   +-- requests.py
    |   |   +-- workers.py
    |   +-- database/
    |   |   +-- connection.py
    |   |   +-- models/
    |   |   +-- repositories/
    |   +-- services/
    |
    +-- infrastructure/
    |   +-- supabase_client.py
    |   +-- qdrant_client.py
    |
    +-- processing/docling/
    |   +-- converter.py
    |   +-- pipeline.py
    |   +-- heading_extractor.py
    |   +-- toc_analyzer.py
    |   +-- hierarchy_builder.py
    |   +-- element_processor.py
    |   +-- image_processor.py
    |   +-- table_processor.py
    |   +-- context_enricher.py
    |   +-- chunk_builder.py
    |
    +-- embeddings/
    |   +-- bge_embedder.py
    |   +-- siglip_embedder.py
    |   +-- document_embedder.py
    |   +-- query_embedder.py
    |
    +-- retrieval/
    |   +-- vector_store.py
    |   +-- retriever.py
    |   +-- filters.py
    |
    +-- rag/
    |   +-- orchestrator.py
    |   +-- state.py
    |   +-- tools/
    |   |   +-- base.py
    |   |   +-- registry.py
    |   |   +-- search_text.py
    |   |   +-- search_image.py
    |   |   +-- search_table.py
    |   |   +-- search_code.py
    |   |   +-- search_formula.py
    |   |   +-- search_headings.py
    |   +-- stages/
    |   |   +-- intent_analyzer.py
    |   |   +-- query_decomposer.py
    |   |   +-- tool_selector.py
    |   |   +-- result_filter.py
    |   |   +-- context_expander.py
    |   |   +-- sufficiency_checker.py
    |   |   +-- query_rewriter.py
    |   |   +-- answer_generator.py
    |   +-- prompts/
    |
    +-- models/
    |   +-- base.py
    |   +-- factory.py
    |   +-- api_model.py
    |   +-- finetuned_model.py
    |
    +-- workers/
    |   +-- local/
    |   |   +-- database_worker.py
    |   |   +-- llm_worker.py
    |   +-- colab/
    |       +-- docling_worker.py
    |       +-- embedding_worker.py
    |       +-- qwen_worker.py
    |
    +-- notebooks/
    |   +-- docling_colab.ipynb
    |   +-- embedding_colab.ipynb
    |
    +-- tests/

## 5. FastAPI

FastAPI chỉ là điểm giao tiếp, không chứa trực tiếp thuật toán Docling, embedding hoặc RAG.

Endpoint dự kiến:

- POST /auth/register
- POST /auth/login
- GET /auth/me
- POST /documents
- GET /documents
- GET /documents/{document_id}
- DELETE /documents/{document_id}
- GET /documents/{document_id}/status
- POST /chat/sessions
- GET /chat/sessions
- GET /chat/sessions/{session_id}/messages
- POST /chat/sessions/{session_id}/messages
- GET /requests/{request_id}
- POST /workers/jobs/poll
- POST /workers/jobs/{job_id}/start
- POST /workers/jobs/{job_id}/progress
- POST /workers/jobs/{job_id}/complete
- POST /workers/jobs/{job_id}/fail

Streamlit chỉ gọi FastAPI, không truy cập trực tiếp PostgreSQL, Qdrant hoặc khóa dịch vụ.

## 6. PostgreSQL

DBeaver chỉ là công cụ quản lý PostgreSQL.

### users

- id
- username
- password_hash
- created_at

### documents

Một PDF do người dùng tải lên.

- id
- user_id
- file_name
- storage_url
- status
- created_at

### chat_sessions

Một cuộc hội thoại thuộc về người dùng.

- id
- user_id
- document_id, có thể rỗng
- title
- created_at

### messages

- id
- session_id
- role: user, assistant hoặc system
- content
- image_url, có thể rỗng
- created_at

Người hỏi được xác định qua messages.session_id -> chat_sessions.user_id.

### rag_requests

Một lần xử lý câu hỏi.

- id
- session_id
- user_message_id
- status
- current_stage
- final_answer
- error
- created_at
- completed_at

### rag_subtasks

Các truy vấn con do router tạo.

- id
- rag_request_id
- tool_name
- query
- target_collection
- document_id
- page_filter
- status
- result
- created_at

### processing_jobs

Tác vụ nền như Docling, embedding hoặc lưu Qdrant.

- id
- user_id
- document_id
- job_type
- status
- worker_id
- input_payload
- output_payload
- progress
- error
- attempt_count
- created_at
- started_at
- completed_at

active_requests trong RAM của tab_llm_worker.py sẽ được thay bằng rag_requests và rag_subtasks. Qdrant payload phải chứa tối thiểu user_id, document_id và chunk_id.

## 7. Tool và stage RAG

Tool hiện có:

- search_text
- search_image
- search_table
- search_code
- search_formula
- search_headings

Đếm, lấy toàn bộ, lọc trang và lọc tài liệu là tham số của tool. Tool được đăng ký trong rag/tools/registry.py. Orchestrator và tool selector phải tự đọc registry để không cần sửa code lõi khi thêm tool.

Các stage:

1. Intent analyzer.
2. Query decomposer.
3. Tool selector.
4. Result filter.
5. Context expander.
6. Sufficiency checker.
7. Query rewriter.
8. Answer generator.

Mỗi stage nhận model và prompt từ config/pipeline.yaml. Có thể đổi riêng một stage từ API sang model fine-tuned.

## 8. Tách docling.ipynb

- Cell 11-17 -> heading_extractor.py
- Cell 23-29 -> toc_analyzer.py
- Cell 31-49 -> hierarchy_builder.py
- Cell 51-59 -> element_processor.py, image_processor.py và table_processor.py
- Cell 61, hàm find_heading -> pipeline.py
- Cell 63 -> context_enricher.py, image_processor.py, table_processor.py và chunk_builder.py
- Cell 68 -> workers/colab/docling_worker.py
- Cell 73 -> test
- Cell thử nghiệm, code comment và code trùng -> xóa sau khi đối chiếu kết quả

bridge_module.py được giải thể sau khi các hàm đã chuyển vào processing/docling.

### Logic sửa nhận diện nhầm bắt buộc phải giữ nguyên

Các bước dưới đây là một phần của thuật toán Docling cũ, không phải code thử nghiệm và không được lược bỏ khi tách module:

- Phát hiện `text`, `list_item` hoặc `table` dùng font monospace với tỷ lệ đạt ngưỡng rồi chuyển thành `code` (`convert_monospace_text_to_code`).
- Phát hiện vùng `picture` chứa code monospace; tách riêng phần code và phần ảnh, hoặc đổi toàn bộ vùng thành code khi phù hợp (`split_picture_containing_code`).
- Sửa phần tử bị nhận là `table` nhưng caption bắt đầu bằng "hình" hoặc "figure" thành `picture` (`fix_tables_misidentified_as_pictures`).
- Gộp các `picture` bị Docling chia nhỏ dựa trên tọa độ và vật cản nằm giữa (`merge_pictures_by_coordinates`).
- Lọc các `text`/`list_item` bị nghi là heading ra khỏi danh sách element để tránh vừa là heading vừa là nội dung (`filter_suspects_from_elements`).
- Loại heading dùng font monospace bị nhận nhầm và đưa nội dung cần thiết trở lại danh sách element (`filter_monospace_headings`, `resolve_removed_headings`).
- Giữ nguyên thứ tự gọi các bước sửa nhầm trong `find_heading`; không được chỉ sao chép hàm mà bỏ việc nối chúng vào pipeline.

Các hàm này nằm chủ yếu trong `processing/docling/element_processor.py`, `processing/docling/hierarchy_builder.py` và được điều phối bởi `processing/docling/pipeline.py`. Test trích xuất phải tiếp tục đối chiếu AST với `docling.ipynb`; kiểm thử PDF mẫu vẫn là bước bắt buộc để xác nhận hành vi đầu-cuối.

## 9. Vấn đề đã phát hiện

- app_ui.py chưa có đăng nhập.
- Supabase secret từng được ghi trực tiếp trong source; phải thu hồi/đổi và chuyển sang biến môi trường.
- tab_docling_worker.py gọi nhiều hàm nhưng không import, nên chưa chạy độc lập.
- bridge_module.py trùng logic notebook.
- Notebook mang tên SigLIP2 nhưng worker cuối đang dùng google/siglip-base-patch16-224; cần thống nhất model.
- Formula chunk lưu nội dung trong latex và code chunk lưu trong code_raw, nhưng embedding hiện đọc content; cần chuẩn hóa schema.
- active_requests và conversation_history đang ở RAM, không phù hợp khi chạy nhiều process hoặc nhiều người dùng.
- Colab có thể ngắt phiên; job phải được lưu bền vững và hỗ trợ retry/idempotency.

## 10. Nguyên tắc triển khai

- Không tái cấu trúc toàn bộ và thêm FastAPI cùng một lúc.
- Giữ hành vi hiện tại trước khi tối ưu thuật toán.
- Logic xử lý trong docling.ipynb là ràng buộc bất biến: khi tách file chỉ được di chuyển code, bổ sung import và đóng gói module; không thay thuật toán, điều kiện, ngưỡng, thứ tự xử lý hoặc cấu trúc dữ liệu đầu ra nếu chưa có sự đồng ý rõ ràng của chủ dự án.
- Trước và sau khi tách Docling phải chạy cùng một bộ PDF mẫu, rồi đối chiếu số lượng chunk, loại chunk, heading, tọa độ, caption, context và nội dung JSON để chứng minh kết quả tương đương.
- Worker chỉ nhận job, gọi module nghiệp vụ và trả trạng thái.
- Logic nghiệp vụ không nằm trực tiếp trong endpoint.
- Không để secret trong source hoặc notebook.
- Dùng ID và user_id xuyên suốt để chống lẫn dữ liệu.
- Mỗi giai đoạn phải có test trước khi xóa file cũ.

## 11. Thứ tự thực hiện

1. Chuẩn hóa config, secret và schema dùng chung.
2. Thêm PostgreSQL models, migration và repositories.
3. Tạo FastAPI cho auth, document, chat, request và worker job.
4. Sửa Streamlit để chỉ gọi FastAPI.
5. Tách docling.ipynb thành module nhưng giữ output tương thích.
6. Tách embedding notebook và sửa schema code/formula.
7. Tách tab_llm_worker.py thành tool, stage và orchestrator.
8. Chuyển active_requests và lịch sử chat sang PostgreSQL.
9. Hoàn thiện worker Colab lấy/trả job qua FastAPI.
10. Thêm kiểm thử tích hợp, sau đó xóa code trùng và file cũ.

## 12. Việc chưa chốt

- ORM và công cụ migration cho PostgreSQL.
- Cơ chế xác thực worker Colab.
- Cách công khai FastAPI từ máy cá nhân.
- Giữ Firestore tạm thời hay thay hoàn toàn bằng PostgreSQL job queue.
- Model fine-tuned cụ thể cho từng stage.
- Cơ chế nhiều worker claim job an toàn.
