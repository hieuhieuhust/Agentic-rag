# PROJECT CONTEXT UPDATE

Tài liệu này ghi lại những điểm được bổ sung hoặc cần điều chỉnh so với kiến trúc cũ. Nội dung nền đầy đủ vẫn nằm trong `PROJECT_CONTEXT.md`.

## 1. Mục tiêu cập nhật

- Giữ một backend FastAPI dùng chung cho Streamlit, web và ứng dụng di động.
- Cho phép nhiều người dùng sử dụng đồng thời mà không làm lẫn dữ liệu hoặc khiến server treo khi quá tải.
- Tận dụng máy cá nhân và Google Colab trong giai đoạn demo; chưa bắt buộc đưa toàn bộ hệ thống lên cloud.
- Tối ưu tài nguyên bằng hàng đợi, worker pool, batching, cache và model nhỏ/fine-tuned.

## 2. Những phần giữ nguyên

- PostgreSQL chạy trên máy và được quản lý bằng DBeaver.
- Qdrant có thể chạy ở bất kỳ đâu miễn FastAPI và worker truy cập được.
- Supabase Storage giữ PDF, ảnh và dữ liệu trung gian.
- Google Colab cung cấp GPU cho Docling và embedding trong giai đoạn demo.
- Streamlit tiếp tục là giao diện thử nghiệm trước khi làm web hoặc ứng dụng điện thoại.
- FastAPI là điểm giao tiếp chung; frontend không chứa logic nghiệp vụ.
- Logic xử lý trong `docling.ipynb`, đặc biệt các bước sửa nhận diện nhầm, là bất biến nếu chưa được chủ dự án đồng ý thay đổi.

## 3. Những phần đã bổ sung trong `gen`

- Backend FastAPI cho đăng ký, đăng nhập, tài liệu, phiên chat, tin nhắn, RAG request và worker job.
- PostgreSQL models cho `users`, `documents`, `chat_sessions`, `messages`, `rag_requests`, `rag_subtasks` và `processing_jobs`.
- JWT để xác thực người dùng.
- Job có cơ chế claim, lease, cập nhật tiến độ, hoàn thành, thất bại và retry.
- Chuỗi xử lý tài liệu: `Docling -> Embedding -> Index Qdrant`.
- Docling được tách thành các module nhưng giữ nguyên thuật toán và thứ tự xử lý cũ.
- Các stage Agentic RAG và tool tìm kiếm được tách riêng để có thể thay model hoặc thêm tool.
- Streamlit gọi backend thông qua `frontend/api_client.py`.

## 4. Những điểm cần chỉnh sửa so với hệ thống cũ

### 4.1. Trạng thái RAG

- Loại bỏ `active_requests` và `conversation_history` lưu trong RAM của `tab_llm_worker.py`.
- Lưu trạng thái lâu dài bằng `rag_requests`, `rag_subtasks` và `messages` trong PostgreSQL.
- Chuyển đầy đủ các trường còn thiếu như số vòng lặp, cờ loại truy vấn, kết quả trung gian và chunk được chọn sang schema mới.
- Hoàn thiện RAG worker mới để thay thế toàn bộ luồng nhiều chặng trong `tab_llm_worker.py`.

### 4.2. Cách ly dữ liệu người dùng

- Mọi tài liệu, phiên chat, tin nhắn, request và job phải truy ngược được tới `users.id`.
- Mọi endpoint phải kiểm tra tài nguyên có thuộc người dùng đang đăng nhập hay không.
- Qdrant payload phải có tối thiểu `user_id`, `document_id` và `chunk_id`.
- Mọi truy vấn Qdrant bắt buộc lọc theo người dùng và tài liệu phù hợp.

### 4.3. Xử lý bất đồng bộ

- Upload PDF hoặc gửi câu hỏi tạo job rồi trả `job_id`/`request_id` ngay.
- Không giữ HTTP request mở trong suốt thời gian Docling, embedding hoặc RAG chạy.
- Giao diện dùng polling trước; WebSocket có thể bổ sung sau.
- Trạng thái hiển thị gồm: chờ, đang xử lý, hoàn thành và thất bại.

## 5. Phương án phục vụ nhiều người dùng

### 5.1. PostgreSQL Job Queue

- PostgreSQL là nguồn trạng thái chính và hàng đợi trong bản demo.
- Worker nhận việc bằng `claim + lease` và khóa hàng phù hợp để tránh hai worker xử lý cùng một job.
- Job hết lease được phép nhận lại; retry phải có giới hạn.
- Mọi thao tác hoàn thành phải idempotent để chạy lại không tạo vector hoặc dữ liệu trùng.

### 5.2. Worker pool

- Tách hàng đợi theo `docling`, `embedding`, `index` và `rag`.
- Có thể mở nhiều Colab worker; mỗi worker nhận một job khác nhau.
- Mỗi GPU chỉ chạy số job đồng thời phù hợp, mặc định một job Docling nặng tại một thời điểm.
- Model được tải một lần và giữ trong RAM/GPU để xử lý nhiều job nối tiếp.

### 5.3. Backpressure và công bằng

- Job dư phải chờ trong hàng đợi thay vì tiếp tục đẩy vào GPU.
- Giới hạn kích thước PDF, tần suất request và số job đang chạy của từng người dùng.
- Trong bản demo, mỗi người dùng chỉ nên có tối đa một PDF đang xử lý.
- Lập lịch luân phiên giữa người dùng để một người không chiếm toàn bộ worker.
- Ưu tiên truy vấn chat ngắn hơn job xử lý PDF mới, nhưng không để job PDF bị chờ vô hạn.

### 5.4. Tối ưu tài nguyên

- Batch các chunk khi tạo embedding.
- Cache kết quả xử lý PDF, embedding và các kết quả có thể tái sử dụng.
- Không xử lý lại tài liệu nếu checksum và cấu hình pipeline không thay đổi.
- Dùng model nhỏ/fine-tuned cho phân tích ý định, phân rã câu hỏi, chọn tool/collection và viết lại truy vấn.
- Có thể dùng reranker nhỏ chuyên dụng cho bước lọc kết quả.
- Chỉ dùng model mạnh cho câu trả lời cuối hoặc câu hỏi cần suy luận phức tạp.
- Giới hạn số truy vấn con, số vòng Agentic RAG, số chunk và tổng token đưa vào model.

### 5.5. FastAPI và PostgreSQL

- Cấu hình connection pool cho PostgreSQL.
- Phân trang danh sách tài liệu, phiên chat và tin nhắn.
- Endpoint ngắn, không chạy trực tiếp Docling, embedding hoặc inference nặng.
- Có thể chạy nhiều FastAPI process sau khi mọi trạng thái đã được đưa ra khỏi RAM.
- Bổ sung rate limit, timeout và giới hạn payload.

## 6. Cấu hình demo dự kiến

- Máy cá nhân: FastAPI, PostgreSQL, Qdrant và local index worker.
- Google Colab 1: Docling worker.
- Google Colab 2: embedding worker.
- Supabase Storage: PDF, ảnh, chunk JSON và dữ liệu trung gian.
- Cloudflare Tunnel hoặc ngrok: cung cấp HTTPS để app/web và Colab gọi FastAPI trên máy.
- Có thể mở thêm Colab worker nếu tài nguyên và giới hạn phiên cho phép.

Khi máy cá nhân, tunnel hoặc Qdrant tắt, job phải chuyển sang trạng thái chờ/thử lại thay vì mất dữ liệu.

## 7. Web và ứng dụng điện thoại

- Không viết lại backend riêng cho mobile.
- Streamlit, web và mobile dùng chung FastAPI và cùng cơ chế JWT.
- Backend cần bổ sung refresh token, đăng xuất, phân trang, upload file lớn, HTTPS và API xóa dữ liệu trước khi phát hành thực tế.
- Mobile có thể bổ sung push notification khi PDF hoặc câu trả lời xử lý xong.

## 8. Kế hoạch Agent Harness và MCP

Hiện tại `rag/orchestrator.py`, `rag/stages/`, `rag/tools/registry.py`, cấu hình pipeline và các bảng trạng thái mới chỉ tạo thành khung ban đầu. Chưa có một Agent Harness hoàn chỉnh và chưa tích hợp MCP.

### 8.1. Chuẩn hóa interface tool

- Sửa `rag/tools/base.py` để mọi tool dùng chung interface bất đồng bộ dạng `execute(context, arguments)`.
- Tạo `ToolContext` chứa tối thiểu `user_id`, `document_id`, `request_id`, quyền truy cập và thông tin trace.
- Tạo `ToolResult` chứa dữ liệu trả về, nguồn tham chiếu, artifact, lỗi và thời gian thực thi.
- Sửa `rag/tools/registry.py` để quản lý được cả tool Python nội bộ và tool lấy từ MCP.
- Sửa `rag/stages/tool_selector.py` để đọc tên, mô tả và input schema động từ registry thay vì phụ thuộc vào danh sách tool ghi cứng.
- Tool không được tự lấy trạng thái toàn cục; mọi dữ liệu theo người dùng phải đi qua `ToolContext`.

### 8.2. Bổ sung Agent Harness

Dự kiến thêm cấu trúc:

```text
rag/runtime/
|-- harness.py
|-- run_context.py
|-- loop_controller.py
|-- tool_executor.py
|-- policies.py
+-- tracing.py
```

Harness chịu trách nhiệm:

- Tải và lưu trạng thái RAG bằng PostgreSQL.
- Điều khiển toàn bộ vòng lặp Agentic RAG.
- Gọi orchestrator, các stage và tool executor.
- Giới hạn số vòng, số tool call, token, thời gian và chi phí.
- Thực hiện timeout, retry, hủy request và xử lý lỗi.
- Ghi lại từng bước và tạo câu trả lời cuối.

`rag/orchestrator.py` chỉ chịu trách nhiệm lập kế hoạch và quyết định bước tiếp theo; harness chịu trách nhiệm vận hành và duy trì trạng thái. RAG worker sẽ gọi harness thay vì giữ `active_requests` trong RAM.

### 8.3. Dự trù tích hợp MCP

Dự kiến thêm cấu trúc:

```text
integrations/mcp/
|-- client.py
|-- tool_adapter.py
|-- server_manager.py
|-- config.py
+-- mcp_server.py        # Chỉ cần khi muốn công khai tool của hệ thống
```

- `McpToolAdapter` chuyển tool MCP về cùng interface với `RagTool`.
- Harness không cần biết tool được chạy nội bộ hay đến từ MCP server.
- Khai báo MCP server, transport, timeout và danh sách tool cho phép trong file cấu hình.
- Hỗ trợ whitelist, kiểm tra quyền theo người dùng và yêu cầu xác nhận với tool nhạy cảm.
- MCP client dùng để gọi tool bên ngoài; MCP server chỉ bổ sung khi muốn hệ thống khác gọi các tool của dự án.
- MCP không thay thế FastAPI, PostgreSQL, job queue hoặc worker; nó chỉ chuẩn hóa cách agent kết nối và gọi công cụ.

Các tool dài như tạo PowerPoint hoặc video phải tạo `processing_job`, chạy trong worker riêng và trả artifact qua Storage, không chạy trực tiếp trong HTTP request hoặc vòng lặp agent.

### 8.4. Dữ liệu theo dõi tool

`rag_subtasks` cần xem xét bổ sung:

- `tool_source`: local hoặc MCP.
- `tool_call_id`.
- `input_payload`, `output_payload`.
- `started_at`, `completed_at`, `duration_ms`.
- `error` và `approval_status`.

Frontend chỉ cần thay đổi khi muốn hiển thị tool đang chạy, nguồn tham chiếu, tiến độ, yêu cầu xác nhận hoặc file artifact để tải xuống.

### 8.5. Thứ tự triển khai Harness và MCP

1. Chuẩn hóa interface và schema của tool nội bộ.
2. Xây Agent Harness và lưu đầy đủ trạng thái vào PostgreSQL.
3. Chuyển logic `tab_llm_worker.py` sang harness mới.
4. Hoàn thiện test cho vòng lặp, giới hạn, lỗi và quyền truy cập.
5. Thêm MCP client và adapter sau khi interface tool nội bộ đã ổn định.
6. Chỉ thêm MCP server khi thực sự cần công khai tool cho hệ thống khác.

## 9. Kiểm thử và tiêu chí đánh giá

### 9.1. Kiểm thử chức năng

- Đăng ký, đăng nhập và phân quyền.
- Upload PDF và theo dõi toàn bộ chuỗi job.
- Đối chiếu đầu ra Docling cũ và mới trên cùng bộ PDF.
- Kiểm tra embedding, lưu Qdrant, truy xuất và trả lời cuối.
- Kiểm tra retry, lease hết hạn và worker bị ngắt giữa chừng.

### 9.2. Kiểm thử nhiều người dùng

- Chạy lần lượt 5, 10 và 20 người dùng đồng thời.
- Kiểm tra không lẫn document, chunk, phiên chat và câu trả lời giữa các tài khoản.
- Đo thời gian phản hồi API, thời gian chờ job, thời gian xử lý, throughput và tỷ lệ lỗi.
- Theo dõi CPU, RAM, GPU, PostgreSQL connections và Qdrant latency.
- Kiểm tra hệ thống vẫn nhận job và phục hồi được khi Colab mất kết nối.

### 9.3. Đánh giá tối ưu Agentic RAG

- So sánh RAG thông thường với Agentic RAG.
- So sánh model lớn với model nhỏ/fine-tuned ở từng stage.
- Đo chất lượng truy xuất, tính đúng và trung thực của câu trả lời.
- Đo số lần gọi model, tổng token, độ trễ và chi phí cho mỗi câu hỏi.

## 10. Thứ tự triển khai cập nhật

1. Hoàn thiện schema PostgreSQL cho trạng thái RAG còn thiếu.
2. Chuẩn hóa interface tool, `ToolContext`, `ToolResult` và registry động.
3. Xây Agent Harness và lưu toàn bộ vòng đời RAG vào PostgreSQL.
4. Chuyển toàn bộ `tab_llm_worker.py` sang RAG worker mới và loại bỏ trạng thái RAM.
5. Hoàn thiện kiểm tra quyền ở API và bộ lọc Qdrant theo người dùng.
6. Hoàn thiện chuỗi job Docling, embedding và index bằng dịch vụ thật.
7. Thêm backpressure, giới hạn theo người dùng, retry và idempotency.
8. Thêm batching, cache và giới hạn số vòng Agentic RAG.
9. Kiểm thử đầu-cuối bằng PDF mẫu trên hai Colab worker.
10. Load test với 5, 10 và 20 người dùng; điều chỉnh giới hạn theo kết quả thực tế.
11. Thêm MCP client/adapter; chỉ tạo MCP server khi có nhu cầu công khai tool.
12. Giữ Streamlit cho demo, sau đó phát triển web hoặc mobile dùng chung API.
13. Chỉ chuyển PostgreSQL, Qdrant và backend lên cloud khi cần vận hành ổn định ngoài phạm vi demo.

## 11. Giới hạn cần ghi rõ

- Hàng đợi không làm phần cứng mạnh hơn; nó đổi việc quá tải thành thời gian chờ có kiểm soát.
- Google Colab phù hợp thử nghiệm và demo ngắn, không bảo đảm chạy liên tục cho production.
- Khả năng phục vụ đồng thời thực tế chỉ được kết luận sau load test.
- Không thay đổi thuật toán Docling để đổi lấy tốc độ nếu chưa có kiểm thử tương đương và sự đồng ý rõ ràng.
