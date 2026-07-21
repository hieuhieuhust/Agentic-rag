import time
import json
import gzip
import urllib.request
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Nạp các hàm từ file database_manager.py (cùng thư mục)
import database_manager

# 1. KẾT NỐI FIREBASE & QDRANT
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except ValueError:
    pass
db = firestore.client()

# Khởi tạo Qdrant Client (chạy ở Local)
qdrant_client = database_manager.get_qdrant_client()
database_manager.init_collections(qdrant_client)

print(" Tab Database Worker đã khởi động thành công!")

# LISTENER 1: NHẬN JSON ĐÃ NHÚNG TỪ EMBEDDING -> LƯU VÀO QDRANT
def on_docling_db_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED']:
            doc_data = change.document.to_dict()
            doc_id = change.document.id
            
            if doc_data.get("status") == "pending":
                document_id = doc_data.get("document_id")
                print(f"\n[DB WORKER] Nhận lệnh lưu DB cho tài liệu: {document_id}")
                
                db.collection("docling_to_db_tasks").document(doc_id).update({"status": "processing"})
                
                # Báo cho UI biết đang lưu vào Database
                db.collection("ui_to_docling_tasks").document(document_id).update({"status": "db_processing"})
                
                try:
                    # 1. Tải file JSON nén đã nhúng từ Supabase
                    embedded_json_url = doc_data.get("embedded_json_url")
                    print(f"  -> Đang tải file JSON nén từ Supabase: {embedded_json_url}")
                    
                    local_embedded_path = f"temp_embedded_{document_id}.json.gz"
                    urllib.request.urlretrieve(embedded_json_url, local_embedded_path)
                    
                    # Giải nén Gzip
                    with gzip.open(local_embedded_path, 'rt', encoding='utf-8') as f:
                        json_chunks = json.load(f)
                    
                    # 2. Lưu từng chunk vào 5 Tủ Qdrant tương ứng
                    print("  -> Đang nạp vào Qdrant Local...")
                    
                    for chunk in json_chunks.get("text_chunks", []):
                        database_manager.luu_vao_vector_db(qdrant_client, "text_chunks", chunk)
                        
                    for chunk in json_chunks.get("table_chunks", []):
                        database_manager.luu_vao_vector_db(qdrant_client, "table_chunks", chunk)
                        
                    for chunk in json_chunks.get("formula_chunks", []):
                        database_manager.luu_vao_vector_db(qdrant_client, "formula_chunks", chunk)
                        
                    for chunk in json_chunks.get("code_chunks", []):
                        database_manager.luu_vao_vector_db(qdrant_client, "code_chunks", chunk)
                        
                    for chunk in json_chunks.get("image_chunks", []):
                        vec = chunk.get('embedding_image', [])
                        if vec:
                            print(f"    [K.TRA ẢNH] {chunk.get('chunk_id')} | 3 số đầu vector: {vec[:3]}")
                        database_manager.luu_vao_vector_db(qdrant_client, "image_chunks", chunk)
                        
                    for chunk in json_chunks.get("intro_chunks", []):
                        database_manager.luu_vao_vector_db(qdrant_client, "intro_and_heading", chunk)
                        
                    # 3. Báo cáo hoàn thành (Để UI hiển thị xanh lá cây)
                    print("  -> Đã nạp thành công toàn bộ dữ liệu vào Qdrant!")
                    db.collection("docling_to_db_tasks").document(doc_id).update({"status": "done"})
                    
                    # Cập nhật trạng thái tổng để UI biết là xong 100%
                    db.collection("ui_to_docling_tasks").document(document_id).update({"status": "db_done"})
                    
                    # Xóa file rác
                    if os.path.exists(local_embedded_path):
                        os.remove(local_embedded_path)
                        
                except Exception as e:
                    print(f"[LỖI LƯU DB]: {e}")
                    db.collection("docling_to_db_tasks").document(doc_id).update({"status": "error", "error": str(e)})
                    
                    # Báo lỗi về UI để ngừng tiến trình
                    if 'document_id' in locals():
                        db.collection("ui_to_docling_tasks").document(document_id).update({
                            "status": "error", 
                            "error": f"Lỗi ở Tab Database: {str(e)}"
                        })

# LISTENER 2: NHẬN CÂU HỎI TỪ EMBEDDING -> TÌM TRONG QDRANT VÀ TRẢ LẠI
def on_embedding_db_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED']:
            doc_data = change.document.to_dict()
            doc_id = change.document.id
            
            if doc_data.get("status") == "pending":
                request_id = doc_data.get("request_id")
                print(f"\n[DB WORKER] Đang tìm kiếm cho câu hỏi của {request_id}...")
                
                db.collection("embedding_to_db_tasks").document(doc_id).update({"status": "processing"})
                
                try:
                    query_vector = doc_data.get("query_vector")
                    target_collection = doc_data.get("target_collection")
                    target_document_id = doc_data.get("target_document_id", "ALL")
                    page_filter = doc_data.get("page_filter")
                    sub_tracking = doc_data.get("sub_tracking")
                    
                    is_counting_query = doc_data.get("is_counting_query", False)
                    is_fetch_all_content = doc_data.get("is_fetch_all_content", False)
                    
                    if is_counting_query:
                        print(f"  -> [ANALYTICAL RAG] Đang đếm và liệt kê (Bypass Vector)...")
                        ket_qua_dem = database_manager.dem_va_lay_du_lieu_bang_filter(
                            client=qdrant_client,
                            collection_name=target_collection,
                            target_document_id=target_document_id,
                            page_filter=page_filter,
                            limit=50
                        )
                        # Trả về mảng các items để tương thích với cấu trúc của llm_worker
                        ket_qua_tim_kiem = ket_qua_dem["items"]
                        total_count = ket_qua_dem["count"]
                        print(f"  -> Đã đếm ra {total_count} kết quả phù hợp (Page Filter: {page_filter}). Đang gửi về cho LLM...")
                    elif is_fetch_all_content:
                        print(f"  -> [FETCH ALL] Đang lấy TOÀN BỘ nội dung từ Tủ '{target_collection}' (Bypass Vector)...")
                        ket_qua_dem = database_manager.dem_va_lay_du_lieu_bang_filter(
                            client=qdrant_client,
                            collection_name=target_collection,
                            target_document_id=target_document_id,
                            page_filter=page_filter,
                            limit=50
                        )
                        ket_qua_tim_kiem = ket_qua_dem["items"]
                        total_count = ket_qua_dem["count"]
                        print(f"  -> [FETCH ALL] Đã lấy {total_count} đối tượng có nội dung đầy đủ (Page Filter: {page_filter}). Đang gửi về cho LLM...")
                    else:
                        # Quyết định chọn hộc Vector nào để tìm kiếm
                        vector_name = None
                        if target_collection == "image_chunks":
                            # Tự động phán đoán dựa vào chiều dài của vector (SigLIP = 768, BGE-M3 = 1024)
                            if len(query_vector) == 768:
                                vector_name = "embedding_image"
                            else:
                                vector_name = "embedding_caption"
                                
                        elif target_collection == "table_chunks":
                            # Định tuyến dựa vào cờ LLM truyền xuống
                            table_query_type = doc_data.get("table_query_type")
                            if table_query_type == "content":
                                vector_name = "embedding_content"
                            else:
                                vector_name = "embedding_caption"
                        
                        # Gọi hàm tìm kiếm
                        ket_qua_tim_kiem = database_manager.tim_kiem_vector_db(
                            client=qdrant_client,
                            collection_name=target_collection,
                            query_vector=query_vector,
                            vector_name=vector_name,
                            top_k=5,
                            target_document_id=target_document_id,
                            page_filter=page_filter
                        )
                        print(f"  -> Đã tìm ra {len(ket_qua_tim_kiem)} kết quả phù hợp (Page Filter: {page_filter}). Đang gửi về cho LLM14b...")
                    
                    print(f"  -> Đã tìm ra {len(ket_qua_tim_kiem)} kết quả phù hợp (Page Filter: {page_filter}). Đang gửi về cho LLM14b...")
                    
                    # Gửi kết quả thẳng sang hộp thư của LLM14b (hoặc LLM Worker)
                    db.collection("db_to_llm14b_results").document(doc_id).set({
                        "request_id": request_id,
                        "search_results": ket_qua_tim_kiem,
                        "is_counting_query": is_counting_query,
                        "total_count": total_count if is_counting_query else len(ket_qua_tim_kiem),
                        "target_collection": target_collection,
                        "sub_tracking": sub_tracking,
                        "status": "pending",
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                    
                    db.collection("embedding_to_db_tasks").document(doc_id).update({"status": "done"})
                    
                except Exception as e:
                    print(f"[LỖI TÌM KIẾM DB]: {e}")
                    db.collection("embedding_to_db_tasks").document(doc_id).update({"status": "error", "error": str(e)})
                    
                    # Gửi kết quả rỗng về LLM để chống kẹt (treo UI)
                    db.collection("db_to_llm14b_results").document(doc_id).set({
                        "request_id": request_id,
                        "search_results": [{"do_chinh_xac": 0, "du_lieu": {"content": f"Lỗi truy vấn Database: {str(e)}"}}] if 'request_id' in locals() else [],
                        "sub_tracking": doc_data.get("sub_tracking", {}),
                        "status": "pending",
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })


# CHẠY VÒNG LẶP VÔ HẠN Ở LOCAL
def start_db_worker():
    print(" Bắt đầu hóng tin từ Tab Embedding... (Bấm Ctrl+C để thoát).")
    
    docling_ref = db.collection("docling_to_db_tasks")
    docling_watch = docling_ref.on_snapshot(on_docling_db_snapshot)
    
    embedding_ref = db.collection("embedding_to_db_tasks")
    embedding_watch = embedding_ref.on_snapshot(on_embedding_db_snapshot)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(" Dừng Tab Database Worker.")

if __name__ == "__main__":
    start_db_worker()
