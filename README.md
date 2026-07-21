# Hệ thống Truy vấn Đa phương thức Agentic RAG (Microservices)

Dự án này là hệ thống Hỏi-Đáp đa phương thức Agentic RAG, được thiết kế chuyên biệt theo dạng phân tán (Microservices) để giải quyết bài toán triển khai trên các thiết bị cá nhân thiếu hụt phần cứng.

Cụ thể, kiến trúc hệ thống được chia nhỏ và phân bổ linh hoạt như sau:
- **Xử lý Dữ liệu (Nặng GPU):** Các tác vụ bóc tách tài liệu dùng docling và nhúng Vector (Embedding) được đẩy lên nhiều tab Google Colab để "mượn" phần cứng xử lý tốc độ cao.
- **Cơ sở dữ liệu Vector:** Qdrant DB được thiết lập chạy trực tiếp trên ổ cứng cục bộ (Local) của máy tính cá nhân để dễ dàng quản lý.
- **Bộ não Điều phối (LLM Agent):** Vận hành tại máy tính cá nhân, gọi API trực tiếp đến OpenAI (hoặc Gemini) để đóng vai trò rẽ nhánh, lập luận và tổng hợp đáp án.
- **Giao diện Người dùng:** Được xây dựng bằng Streamlit chạy trên Local.

Tất cả các trạm phân tán này giao tiếp liên tục với nhau theo thời gian thực thông qua Message Broker là Firebase, đồng thời sử dụng Supabase làm bộ đệm lưu trữ hình ảnh trung gian. Thiết kế này giúp hệ thống sở hữu khả năng suy luận mạnh mẽ, miễn nhiễm với ảo giác mà không đòi hỏi máy tính cá nhân phải trang bị Card đồ họa đắt tiền.

---

## 1. Cấu trúc Mã nguồn

Hệ thống được thiết kế thành các module xử lý độc lập:

```text
├── app_ui.py                 # Giao diện người dùng (Streamlit)
├── tab_llm_worker.py         # Bộ não điều phối trung tâm (LLM Agent Orchestrator)
├── tab_db_worker.py          # Trạm cơ sở dữ liệu (Giao tiếp với Qdrant Vector DB)
├── database_manager.py       # Lớp thao tác cơ sở dữ liệu lõi (HNSW, Hybrid Search)
├── bridge_module.py          # Module hỗ trợ xử lý luồng dữ liệu trung gian
├── docling.ipynb             # Trạm tiền xử lý và bóc tách tài liệu (Chạy trên Colab/GPU)
├── bgem3_siglip2.ipynb       # Trạm chuyển đổi Vector đa phương thức (Chạy trên Colab/GPU)
├── requirements.txt          # Danh sách thư viện phụ thuộc
├── .env.example              # Biểu mẫu cấu hình khóa bảo mật (API Keys)
└── README.md                 # Tài liệu mô tả dự án
```

---

## 2. Hướng dẫn Triển khai

### 2.1. Yêu cầu Hệ thống
Cài đặt các thư viện cần thiết thông qua pip:
```bash
pip install streamlit firebase-admin qdrant-client google-generativeai pypdfium2 openai
```

### 2.2. Cấu hình Môi trường (API & Database)
Đổi tên tệp `.env.example` thành `.env` và thiết lập các thông tin sau:

**1. Firebase Firestore (Message Broker):**
- Truy cập [Firebase Console](https://console.firebase.google.com/), tạo dự án mới và bật dịch vụ **Firestore Database** (Chế độ Test Mode).
- Vào `Project Settings` > `Service Accounts` > Chọn `Generate new private key`.
- Đổi tên tệp tải về thành `serviceAccountKey.json` và đặt vào thư mục gốc của dự án.

**2. Supabase Storage (Lưu trữ ảnh trung gian):**
- Truy cập [Supabase](https://supabase.com/), tạo dự án mới và tạo một Storage Bucket tên là `rag-data` (Bật chế độ Public).
- Lấy `Project URL` và `API Key` dán vào tệp `.env` cũng như trong các tệp `.ipynb` trên Colab.

**3. LLM API Keys:**
- Đăng ký và lấy mã API từ các nhà cung cấp (OpenAI, Google Gemini, Groq...) rồi điền tương ứng vào tệp `.env`.

### 2.3. Khởi động Hệ thống
Thực thi các lệnh sau trên các Terminal riêng biệt để khởi động từng Microservice:

**Terminal 1 (Giao diện người dùng):**
```bash
streamlit run app_ui.py
```

**Terminal 2 (Module Điều phối LLM):**
```bash
python tab_llm_worker.py
```

**Terminal 3 (Module Cơ sở dữ liệu):**
```bash
python tab_db_worker.py
```

Đối với các file `.ipynb` thì phải chạy trên Google Colab:

File `docling.ipynb` thì được chia làm 2 phần chính:
- **Phần 1 luồng chạy chính với hệ thống:** Gồm tất cả các cell hàm và 1 cell sát với **Phần visual**, ở phần này ta sẽ chạy hết các cell bên trên để khởi động hàm, cuối cùng là chạy cell vòng lặp vô hạn để xử lý pdf người dùng đưa vào.
- **Phần 2 phần visual:** Phần này thì chỉ có công dụng visual lại kết quả chạy được của docling và xem logic xử lý có đạt yêu cầu không.
- **API:** Thêm API key tạo từ bên trên vào đây.

File `bgem3_siglip2.ipynb` (hay còn gọi là file embedding) thì cứ thế chạy từ đầu tới cuối.

---

## 3. Tính năng Cốt lõi xây dựng

- **Tiền xử lý Đa phương thức (Docling):** Khả năng bóc tách tài liệu phức tạp, phân loại rành mạch dữ liệu thành 5 phân vùng độc lập: Văn bản (Text), Hình ảnh, Bảng biểu, Mã nguồn (Code) và Công thức toán học. Thêm thuật toán có khả năng chia heading tìm được từ docling thành các cấp bậc và chia các phân vùng độc lập đó vào các mốc heading mới này.
- **Cơ sở dữ liệu Vector (Qdrant DB):** Lưu trữ dữ liệu phân mảnh kết hợp tính năng lọc siêu dữ liệu (Metadata Filtering). Điều này đảm bảo độ chính xác tuyệt đối cho các câu hỏi mang tính thống kê, đếm số lượng (Analytical RAG).
- **Bộ não LLM Agentic:** Đóng vai trò điều phối lõi với 3 năng lực tự chủ:
  1. *Tự động viết lại câu hỏi* (Query Rewriting) để tối ưu hóa truy vấn.
  2. *Tìm kiếm định tuyến* thông qua các hàm công cụ định nghĩa sẵn (Function Calling) để bòn rút dữ liệu tương ứng từ 5 tủ (code, ảnh, text, bảng, công thức).
  3. *Tự đánh giá* (Self-reflection) mức độ chính xác của ngữ cảnh thu được trước khi trả lời.
- **Kiến trúc Microservices (Hướng sự kiện):** Các thành phần hoạt động hoàn toàn độc lập, giao tiếp theo thời gian thực thông qua trạm trung chuyển Firebase Firestore.

---

## 4. Kết quả Đạt được (Tiến độ Hiện tại)
**Sự thật:** Đây là bản đầu tiên khi tôi thử làm với nhiều thành phần trong 1 file pdf (code, bảng biểu, công thức, hình ảnh, text) và cái này là làm đồ án 2 nên thời gian dự kiến ban đầu là 4 tháng nhưng chỉ làm được trong 2 tháng vì sức khỏe nên chỉ mới có thể rút ngắn 1 vài tính năng để thử nghiệm và viết báo cáo đồ án nhưng nó vẫn còn rất rất nhiều không gian mở rộng.

**Về năng lực tiền xử lý tài liệu PDF (Docling):**
- **Trường hợp lý tưởng:** Nếu tài liệu có sẵn cấu trúc Mục lục ẩn (TOC/Bookmarks), hệ thống bóc tách và phân luồng thành công 100%.
- **Trường hợp tài liệu thô:** Nếu PDF không gắn sẵn mục lục nhưng văn bản được trình bày rõ ràng, tính liền mạch giữa các trang cao (đồng nhất về khoảng cách lề, `font-name`, `font-size`), thuật toán vẫn tự động nhận diện và phân rã cấu trúc cực kỳ chính xác.

**Về năng lực suy luận của LLM (LLM Agent):**
Đã nghiệm thu thành công kịch bản truy vấn phức tạp kết hợp Đếm số lượng (Analytical) và Phân tích nội dung đa phương tiện (Multimodal RAG):
- Truy vấn chuỗi (Multi-turn): Hỏi chính xác số lượng bảng biểu, số lượng hình ảnh xuất hiện trong một trang chỉ định.
- Sau khi AI định vị và báo cáo số lượng, tiếp tục truy vấn xoáy sâu vào nội dung chi tiết nằm bên trong chính những bức ảnh/bảng biểu đó (AI vẫn giữ được Context và trả lời xuất sắc).

---

## 5. Khuyến cáo Bảo mật
Vui lòng cấu hình tệp `.gitignore` để loại trừ các tệp chứa thông tin xác thực (`serviceAccountKey.json`), các tệp dữ liệu tạm kích thước lớn (`*.pdf`, `*.json`) và bộ nhớ đệm hệ thống trước khi tải mã nguồn lên các kho lưu trữ công cộng.
