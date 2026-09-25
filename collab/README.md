# Chạy thử worker `gen` trên Google Colab

Thư mục này chỉ chứa notebook khởi động và công cụ đóng gói. Mã xử lý thật vẫn
nằm trong `../gen`; không tạo bản sao logic Docling/embedding để tránh lệch phiên bản.

## 1. Tạo hai gói mã trên máy cá nhân

Từ thư mục `code` chạy:

```powershell
python collab/build_bundles.py
```

Kết quả là `collab/bundles/docling_bundle.zip` và
`collab/bundles/embedding_bundle.zip`. Mỗi gói chỉ chứa các module mà worker
tương ứng cần, cùng `requirements-colab.txt`. Tạo lại gói sau mỗi lần sửa mã
trong `gen`. Các gói không chứa `.env`, key, frontend hay backend.

## 2. Chạy phần máy cá nhân

Trong `gen`, chạy FastAPI, PostgreSQL, Qdrant và database worker như hướng dẫn
trong `gen/README.md`. FastAPI cần có URL HTTPS mà Colab truy cập được; điền URL
đó vào notebook, không điền `localhost`. `WORKER_TOKEN` phải trùng với FastAPI.
Supabase Storage phải truy cập được từ Colab và máy cá nhân.

## 3. Chạy trên Colab

1. Mở `docling_worker.ipynb` trên Colab, chọn GPU, tải lên
   `docling_bundle.zip` và chạy ô cài thư viện. Chọn **Runtime → Restart
   session**, sau đó chạy từ ô cấu hình (không tải bundle/cài lại) tới ô worker.
2. Mở `embedding_worker.ipynb` trong phiên Colab riêng, chọn GPU, tải lên
   `embedding_bundle.zip` và làm tương tự, bao gồm bước restart session.
3. Tải PDF lên Streamlit. Theo dõi trạng thái `docling` → `embedding` →
   `index_qdrant` → `db_done`; database worker trên máy ghi vector vào Qdrant.

Hai ô worker chạy liên tục để nhận job mới. Nếu Colab ngắt phiên, chạy lại
notebook. Colab miễn phí có thể giới hạn số phiên GPU đồng thời; khi đó chạy
từng worker lần lượt, job còn lại sẽ chờ trong PostgreSQL.

Không lưu token hay Supabase key vào notebook hoặc Git. Notebook nhập secret lúc
chạy bằng `getpass`. Với mã hiện tại, URL dữ liệu từ Supabase cần tải được bởi
worker; dùng bucket riêng và dữ liệu thử nghiệm, không dùng PDF nhạy cảm.

**Phạm vi kiểm thử:** luồng nhập PDF đến Qdrant. Luồng hỏi đáp RAG trong `gen`
chưa có worker hoàn chỉnh, nên chưa thể so sánh chất lượng câu trả lời end-to-end.
