import time
import json
import gzip
import urllib.request
import os
import fitz
import firebase_admin
from firebase_admin import credentials, firestore
from supabase import create_client, Client
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

# 1. KẾT NỐI FIREBASE & SUPABASE
# Firebase (Chỉ dùng Firestore làm bưu điện gửi thư)
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except ValueError:
    pass
db = firestore.client()

# Supabase (Kho chứa file khổng lồ thay thế Firebase Storage)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_json_to_supabase(data_dict, file_name):
    # 1. Lưu tạm file JSON ra máy ảo Colab (Dùng Nén Gzip)
    local_path = f"/content/{file_name}.gz"
    with gzip.open(local_path, "wt", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False)
    
    # 2. Bơm file nén lên Supabase
    supabase.storage.from_("rag-data").upload(
        path=f"{file_name}.gz", 
        file=local_path, 
        file_options={"content-type": "application/gzip", "upsert": "true"}
    )
    
    # 3. Lấy đường link public
    public_url = supabase.storage.from_("rag-data").get_public_url(f"{file_name}.gz")
    return public_url

# LISTENER: HÓNG VIỆC TỪ GIAO DIỆN UI
def on_ui_request_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED']:
            doc_data = change.document.to_dict()
            doc_id = change.document.id
            
            if doc_data.get("status") == "pending":
                print(f"\n[DOCLING] Nhận yêu cầu xử lý PDF mới: {doc_data.get('document_id')}")
                db.collection("ui_to_docling_tasks").document(doc_id).update({
                    "status": "docling_processing",
                    "progress_msg": "Đang khởi động thuật toán..."
                })
                
                def update_progress(msg):
                    db.collection("ui_to_docling_tasks").document(doc_id).update({"progress_msg": msg})
                
                try:
                    pdf_url = doc_data.get("pdf_url")
                    doc_ai_id = doc_data.get("document_id")
                    local_pdf_path = f"temp_{doc_ai_id}.pdf"
                    
                    print("  -> 1. Đang tải file PDF từ Cloud về Colab...")
                    update_progress("Bước 1/10: Tải file PDF từ Đám mây về Colab...")
                    urllib.request.urlretrieve(pdf_url, local_pdf_path)
                    
                    print("  -> 2. Bắt đầu chạy bóc tách bằng Docling (Rất nặng, xin chờ)...")
                    update_progress("Bước 2/10: Docling đang đọc từng trang PDF (Mất vài phút)...")
                    pipeline_options = PdfPipelineOptions()
                    pipeline_options.do_ocr = False
                    pipeline_options.do_table_structure = True
                    pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
                    pipeline_options.generate_picture_images = True
                    pipeline_options.images_scale = 2.0

                    converter = DocumentConverter(
                        format_options={
                            InputFormat.PDF: PdfFormatOption(
                                pipeline_options=pipeline_options,
                                backend=PyPdfiumDocumentBackend
                            )
                        }
                    )
                    doc = converter.convert(local_pdf_path).document
                    
                    print("  -> 3. Chạy hàm tổng hợp find_heading của bạn...")
                    update_progress("Bước 3/10: Trích xuất các Tiêu đề (Heading)...")
                    struct_merged, real_heading_muc_luc_level, heading_muc_luc_tree, element_coords, heading_con_sot_giua_2level, removed_headings_log = find_heading(local_pdf_path, doc)
                    
                    print("  -> 4. Chém bỏ phần Mục Lục...")
                    update_progress("Bước 4/10: Đang loại bỏ Mục Lục rác...")
                    element_coords = filter_elements_after_toc(element_coords, struct_merged)
                    
                    print("  -> 5. Gắn gia phả (Heading Path)...")
                    update_progress("Bước 5/10: Khâu nối dữ liệu vào Gia phả...")
                    element_coords = assign_heading_paths(element_coords, struct_merged)
                    
                    print("  -> 6. Gắn ngữ cảnh sát rạt...")
                    update_progress("Bước 6/10: Liên kết ngữ cảnh thông minh...")
                    element_coords = assign_context_snippets(element_coords, max_chars=300)
                    
                    print("  -> 7. Đọc nội dung Bảng theo chiều ngang...")
                    update_progress("Bước 7/10: Trích xuất dữ liệu Bảng...")
                    element_coords = extract_full_table_text(element_coords, doc)
                    
                    print("  -> 8. Cắt ảnh ra từ PDF và tải lên Đám mây...")
                    update_progress("Bước 8/10: Đang cắt Ảnh và Upload (Có thể hơi lâu)...")
                    # Tải ảnh lên Supabase
                    element_coords = crop_and_upload_images(element_coords, local_pdf_path, output_dir=f"/content/cropped_images_{doc_ai_id}", supabase_client=supabase, doc_ai_id=doc_ai_id)
                    
                    print("  -> 9. Đóng gói JSON chia vào 6 tủ (Bao gồm tủ Intro/Heading)...")
                    update_progress("Bước 9/10: Sắp xếp dữ liệu vào 6 Tủ...")
                    json_chunks = package_chunks(element_coords, struct_merged=struct_merged, document_id=doc_ai_id)
                    
                    print("  -> 10. Bơm JSON tổng lên Supabase Storage...")
                    update_progress("Bước 10/10: Đóng gói Gzip và Nén lên Đám mây...")
                    supabase_url = upload_json_to_supabase(json_chunks, f"{doc_ai_id}_raw.json")
                    print(f"       (Đã bơm lên mây tại: {supabase_url})")
                    
                    print("  -> 11. Gắn tag báo cho Tab Embedding vào việc!")
                    db.collection("docling_to_embedding_tasks").document(doc_ai_id).set({
                        "document_id": doc_ai_id,
                        "raw_json_url": supabase_url, # Gửi ĐƯỜNG LINK SUPABASE
                        "status": "pending",
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                    
                    db.collection("ui_to_docling_tasks").document(doc_id).update({"status": "docling_done"})
                    print(f" ĐÃ HOÀN TẤT BÓC TÁCH CHO TÀI LIỆU: {doc_ai_id} \n")
                    
                    # Phát âm thanh báo hiệu xong
                    try:
                        from google.colab import output
                        output.eval_js('new Audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg").play()')
                    except ImportError:
                        pass
                        
                    # DỌN DẸP BỘ NHỚ RAM COLAB
                    print("  -> Đang dọn dẹp bộ nhớ RAM...")
                    del doc
                    del converter
                    del element_coords
                    del struct_merged
                    del json_chunks
                    import gc
                    gc.collect()
                    print("  -> Đã giải phóng RAM, sẵn sàng cho file tiếp theo!")
                    
                except Exception as e:
                    print(f"[LỖI DOCLING]: {e}")
                    db.collection("ui_to_docling_tasks").document(doc_id).update({"status": "error", "error": str(e)})

# CHẠY VÒNG LẶP VÔ HẠN
# Biến global để lưu trữ listener cũ (nếu có)
if 'docling_ui_watch' in globals():
    try:
        docling_ui_watch.unsubscribe()
        print(" Đã dọn dẹp listener cũ đang chạy ngầm.")
    except:
        pass

def start_docling_worker():
    global docling_ui_watch
    print(" Bắt đầu khởi động Tab Docling (Worker)...")
    ui_ref = db.collection("ui_to_docling_tasks")
    docling_ui_watch = ui_ref.on_snapshot(on_ui_request_snapshot)
    print(" Docling đang trực chiến hóng đơn hàng PDF! (Bấm nút Dừng ở Colab để thoát).")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(" Dừng Tab Docling.")
        docling_ui_watch.unsubscribe()

start_docling_worker()
