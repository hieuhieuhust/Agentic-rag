import time
import json
import gzip
import urllib.request
import os
import torch
import requests
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from transformers import AutoProcessor, AutoModel

# KHỞI TẠO AI MODELS (CHẠY TRÊN GPU NẾU CÓ)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f" Đang khởi tạo AI trên thiết bị: {device.upper()}")

print(" Đang tải BGE-M3 (Nhúng Văn bản)...")
# Dùng thư viện sentence_transformers cho nhẹ nhàng và dễ dùng
bgem3_model = SentenceTransformer('BAAI/bge-m3', device=device)

print(" Đang tải SigLIP (Nhúng Hình ảnh)...")
# Dùng bản base của google siglip
siglip_processor = AutoProcessor.from_pretrained("google/siglip-base-patch16-224")
siglip_model = AutoModel.from_pretrained("google/siglip-base-patch16-224").to(device)

print(" Tải xong 2 Model!")

# KẾT NỐI FIREBASE, SUPABASE
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except ValueError:
    pass
db = firestore.client()

# SỬA ĐÚNG 3 DÒNG NÀY VÀO CẢ 2 TAB:
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_json_to_supabase(data_dict, file_name):
    local_path = f"/content/{file_name}.gz"
    with gzip.open(local_path, "wt", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False)

    supabase.storage.from_("rag-data").upload(
        path=f"{file_name}.gz",
        file=local_path,
        file_options={"content-type": "application/gzip", "upsert": "true"}
    )

    public_url = supabase.storage.from_("rag-data").get_public_url(f"{file_name}.gz")
    return public_url

# LISTENER 1: NHẬN JSON TỪ DOCLING -> NHÚNG VÀ TRẢ LẠI
def on_docling_request_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED']:
            doc_data = change.document.to_dict()
            doc_id = change.document.id

            if doc_data.get("status") == "pending":
                document_id = doc_data.get("document_id")
                print(f"\n[EMBEDDING] Nhận lệnh nhúng từ Docling: {document_id}")
                db.collection("docling_to_embedding_tasks").document(doc_id).update({"status": "processing"})
                
                # Báo cho UI biết đang nhúng
                db.collection("ui_to_docling_tasks").document(document_id).update({
                    "status": "embedding_processing",
                    "progress_msg": "Đang khởi động AI Nhúng..."
                })
                
                def update_progress(msg):
                    db.collection("ui_to_docling_tasks").document(document_id).update({"progress_msg": msg})

                try:
                    # 1. Đọc file JSON rỗng từ Supabase URL
                    raw_json_url = doc_data.get("raw_json_url")
                    print(f"  -> Đang tải file raw từ Supabase: {raw_json_url}")
                    update_progress("Bước 1/6: Đang tải dữ liệu từ Đám mây...")

                    local_raw_path = f"/content/raw_{document_id}.json.gz"
                    urllib.request.urlretrieve(raw_json_url, local_raw_path)
                    with gzip.open(local_raw_path, 'rt', encoding='utf-8') as f:
                        json_chunks = json.load(f)

                    # 2. XỬ LÝ NHÚNG VECTOR THẬT CHO 5 TỦ
                    print(f"  -> Đang chạy BGE-M3 và SigLIP để nhúng (Chạy thật trên {device.upper()})...")
                    
                    # -- Tủ Text --
                    update_progress("Bước 2/6: BGE-M3 đang nhúng hàng nghìn mảnh Văn bản...")
                    for chunk in json_chunks.get("text_chunks", []):
                        text_can_nhung = f"Thuộc phần: {chunk.get('heading_path', '')} \n {chunk.get('content', '')}"
                        chunk['embedding'] = bgem3_model.encode(text_can_nhung).tolist()

                    # -- Tủ Bảng --
                    update_progress("Bước 3/6: BGE-M3 đang nhúng dữ liệu Bảng (Dual-Vector)...")
                    for chunk in json_chunks.get("table_chunks", []):
                        text_caption = f"Thuộc phần: {chunk.get('heading_path', '')} \n Bảng: {chunk.get('caption', '')}"
                        chunk['embedding_caption'] = bgem3_model.encode(text_caption).tolist()
                        text_content = f"Nội dung bảng: {chunk.get('table_horizontal_text', '')}"
                        chunk['embedding_content'] = bgem3_model.encode(text_content).tolist()

                    # -- Tủ Công thức --
                    update_progress("Bước 4/6: BGE-M3 đang nhúng Công thức toán...")
                    for chunk in json_chunks.get("formula_chunks", []):
                        text_can_nhung = f"Thuộc phần: {chunk.get('heading_path', '')} \n Công thức: {chunk.get('content', '')}"
                        chunk['embedding'] = bgem3_model.encode(text_can_nhung).tolist()

                    # -- Tủ Code --
                    update_progress("Bước 5/6: BGE-M3 đang nhúng các đoạn Code...")
                    for chunk in json_chunks.get("code_chunks", []):
                        text_can_nhung = f"Thuộc phần: {chunk.get('heading_path', '')} \n Code: {chunk.get('content', '')}"
                        chunk['embedding'] = bgem3_model.encode(text_can_nhung).tolist()

                    # -- Tủ Ảnh --
                    update_progress("Bước 6/6: SigLIP đang nhúng dữ liệu ẢNH qua Supabase...")
                    for chunk in json_chunks.get("image_chunks", []):
                        text_can_nhung = f"Thuộc phần: {chunk.get('heading_path', '')} \n Ảnh: {chunk.get('caption', '')} \n Ngữ cảnh trước: {chunk.get('prev_text_snippet', '')} \n Ngữ cảnh sau: {chunk.get('next_text_snippet', '')}"
                        chunk['embedding_caption'] = bgem3_model.encode(text_can_nhung).tolist()
                        
                        image_ref = chunk.get("image_ref")
                        if image_ref and image_ref.startswith("http") and "firebasestorage" not in image_ref:
                            try:
                                image = Image.open(requests.get(image_ref, stream=True).raw).convert("RGB")
                                inputs = siglip_processor(images=image, return_tensors="pt").to(device)
                                with torch.no_grad():
                                    image_features = siglip_model.get_image_features(**inputs)
                                    if not isinstance(image_features, torch.Tensor):
                                        if hasattr(image_features, 'pooler_output') and getattr(image_features, 'pooler_output') is not None:
                                            image_features = image_features.pooler_output
                                        elif hasattr(image_features, 'image_embeds') and getattr(image_features, 'image_embeds') is not None:
                                            image_features = image_features.image_embeds
                                        elif hasattr(image_features, 'last_hidden_state') and getattr(image_features, 'last_hidden_state') is not None:
                                            image_features = image_features.last_hidden_state.mean(dim=1)
                                        else:
                                            image_features = image_features[0]
                                            if len(image_features.shape) > 2:
                                                image_features = image_features.mean(dim=1)
                                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                                    chunk['embedding_image'] = image_features[0].cpu().numpy().tolist()
                            except Exception as e_img:
                                print(f"     [Cảnh báo] Lỗi tải/nhúng ảnh từ Supabase {image_ref}: {e_img}")
                                chunk['embedding_image'] = [0.0] * 768
                        else:
                            chunk['embedding_image'] = [0.0] * 768

                    # -- Tủ Intro/Heading (Mới) --
                    update_progress("Bước 6.5/6: BGE-M3 đang nhúng cấu trúc Mục lục...")
                    for chunk in json_chunks.get("intro_chunks", []):
                        text_can_nhung = chunk.get('content', '')
                        chunk['embedding'] = bgem3_model.encode(text_can_nhung).tolist()

                    # 3. Bơm file thành phẩm ngược lại Supabase
                    print("  -> Đang bơm kết quả lên Supabase...")
                    update_progress("Hoàn tất nhúng! Đang đóng gói Gzip và đẩy lên đám mây...")
                    embedded_json_url = upload_json_to_supabase(json_chunks, f"{document_id}_embedded.json")

                    # 4. Báo cho Tab Database biết đã xong
                    db.collection("docling_to_db_tasks").document(document_id).set({
                        "document_id": document_id,
                        "embedded_json_url": embedded_json_url,
                        "status": "pending",
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                    print(f"  -> Đã nhúng xong! Báo cho Tab Database tải từ link: {embedded_json_url}")

                    # Báo cho UI biết nhúng xong
                    db.collection("ui_to_docling_tasks").document(document_id).update({"status": "embedding_done"})
                    db.collection("docling_to_embedding_tasks").document(doc_id).update({"status": "done"})

                    # DỌN DẸP BỘ NHỚ RAM COLAB
                    print("  -> Đang dọn dẹp bộ nhớ RAM...")
                    del json_chunks
                    import gc
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    print("  -> Đã giải phóng RAM, VRAM sẵn sàng cho file tiếp theo!")

                except Exception as e:
                    print(f"[LỖI EMBEDDING NẠP]: {e}")
                    db.collection("docling_to_embedding_tasks").document(doc_id).update({"status": "error", "error": str(e)})
                    
                    if 'document_id' in locals():
                        db.collection("ui_to_docling_tasks").document(document_id).update({
                            "status": "error", 
                            "error": f"Lỗi ở Tab Embedding: {str(e)}"
                        })

# LISTENER 2: NHẬN CÂU HỎI TỪ LLM14B -> NHÚNG VÀ BÁO DATABASE TÌM
def on_llm_query_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED']:
            doc_data = change.document.to_dict()
            doc_id = change.document.id

            if doc_data.get("status") == "pending":
                if doc_data.get("trong_pdf") != True:
                    db.collection("llm14b_to_embedding_tasks").document(doc_id).update({"status": "ignored"})
                    continue

                print(f"\n[EMBEDDING RAG] Nhận Sub-Query từ LLM14b: '{doc_data.get('query')}'")
                db.collection("llm14b_to_embedding_tasks").document(doc_id).update({"status": "processing"})

                try:
                    query_text = doc_data.get("query")
                    query_image_url = doc_data.get("query_image_url") # Nhận link ảnh từ LLM (nếu có)
                    is_counting_query = doc_data.get("is_counting_query", False)
                    
                    query_vector = []
                    
                    if is_counting_query:
                        print(f"  -> Nhận truy vấn đếm/liệt kê. Bỏ qua BGE-M3 (Analytical RAG).")
                    elif query_image_url:
                        # Nếu LLM14 gửi yêu cầu tìm kiếm bằng ẢNH -> Dùng não SigLIP
                        print(f"  -> [BƯỚC 1: ĐÓNG CỌC MỎ NEO] Trạm Embedding đang dùng Não thị giác SigLIP để biến Hình Ảnh thành Vector 768 chiều...")
                        image = Image.open(requests.get(query_image_url, stream=True).raw).convert("RGB")
                        inputs = siglip_processor(images=image, return_tensors="pt").to(device)
                        with torch.no_grad():
                            image_features = siglip_model.get_image_features(**inputs)
                            
                            # Lấy vector Tensor từ object trả về siêu an toàn
                            if not isinstance(image_features, torch.Tensor):
                                if hasattr(image_features, 'pooler_output') and getattr(image_features, 'pooler_output') is not None:
                                    image_features = image_features.pooler_output
                                elif hasattr(image_features, 'image_embeds') and getattr(image_features, 'image_embeds') is not None:
                                    image_features = image_features.image_embeds
                                elif hasattr(image_features, 'last_hidden_state') and getattr(image_features, 'last_hidden_state') is not None:
                                    image_features = image_features.last_hidden_state.mean(dim=1)
                                else:
                                    image_features = image_features[0]
                                    if len(image_features.shape) > 2:
                                        image_features = image_features.mean(dim=1)
                                        
                            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                            query_vector = image_features[0].cpu().numpy().tolist()
                    else:
                        # Nếu LLM14 gửi Text -> Dùng não BGE-M3
                        print(f"  -> Nhận truy vấn TEXT từ LLM14: '{query_text[:50]}...'")
                        query_vector = bgem3_model.encode(query_text).tolist()
                    
                    db.collection("embedding_to_db_tasks").document(doc_id).set({
                        "request_id": doc_data.get("request_id"),
                        "query_vector": query_vector,
                        "target_collection": doc_data.get("target_collection"),
                        "target_document_id": doc_data.get("target_document_id", "ALL"),
                        "page_filter": doc_data.get("page_filter"),
                        "table_query_type": doc_data.get("table_query_type"),
                        "is_counting_query": is_counting_query,
                        "sub_tracking": doc_data.get("sub_tracking"),
                        "status": "pending",
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                    print(f"  -> Đã nhúng câu hỏi. Bơm lệnh cho DB quét mục: {doc_data.get('target_collection')}")
                    db.collection("llm14b_to_embedding_tasks").document(doc_id).update({"status": "done"})

                except Exception as e:
                    print(f"[LỖI EMBEDDING RAG]: {e}")
                    db.collection("llm14b_to_embedding_tasks").document(doc_id).update({"status": "error", "error": str(e)})

if 'embedding_docling_watch' in globals():
    try:
        embedding_docling_watch.unsubscribe()
        embedding_llm_watch.unsubscribe()
        print(" Đã dọn dẹp listener cũ đang chạy ngầm.")
    except:
        pass

def start_embedding_worker():
    global embedding_docling_watch, embedding_llm_watch
    print(" Bắt đầu khởi động Tab Embedding (Worker)...")
    
    doc_ref = db.collection("docling_to_embedding_tasks")
    embedding_docling_watch = doc_ref.on_snapshot(on_docling_request_snapshot)

    llm_ref = db.collection("llm14b_to_embedding_tasks")
    embedding_llm_watch = llm_ref.on_snapshot(on_llm_query_snapshot)

    print(" Embedding RAG đang hóng tin từ Docling và LLM14b! (Bấm dừng Colab để thoát).")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(" Dừng Tab Embedding.")
        embedding_docling_watch.unsubscribe()
        embedding_llm_watch.unsubscribe()

start_embedding_worker()
