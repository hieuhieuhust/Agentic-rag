import os
import sys
import io
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue

# Fix console encoding for Windows (Đã tắt để khỏi bị tịt ngòi màn hình Terminal)
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# CẤU HÌNH DATABASE
# Định nghĩa độ dài vector của các model AI
BGE_DIMENSION = 1024 
SIGLIP_DIMENSION = 768

# Đường dẫn lưu trữ thư mục Database ngay trong project
DB_PATH = "./qdrant_db_local"

def get_qdrant_client():
    """Khởi tạo client kết nối tới Qdrant Local"""
    return QdrantClient(path=DB_PATH)

def init_collections(client):
    """Hàm chạy 1 lần duy nhất để tạo ra 5 'tủ khóa' lưu dữ liệu"""
    print("Đang kiểm tra và khởi tạo các Collection...")
    
    danh_sach_collection_don = [
        "text_chunks",
        "formula_chunks",
        "code_chunks",
        "intro_and_heading"
    ]
    
    # 1. Khởi tạo 4 collection cơ bản (Chỉ dùng 1 vector của BGE-M3)
    for col_name in danh_sach_collection_don:
        if not client.collection_exists(col_name):
            client.create_collection(
                collection_name=col_name,
                vectors_config=VectorParams(size=BGE_DIMENSION, distance=Distance.COSINE)
            )
            print(f"[+] Tạo thành công: {col_name}")
        else:
            print(f"[*] Đã tồn tại: {col_name}")
            
    # 2. Khởi tạo collection Hình ảnh (Dùng 2 vector song song: SigLIP cho pixel, BGE cho text)
    if not client.collection_exists("image_chunks"):
        client.create_collection(
            collection_name="image_chunks",
            vectors_config={
                "embedding_caption": VectorParams(size=BGE_DIMENSION, distance=Distance.COSINE),
                "embedding_image": VectorParams(size=SIGLIP_DIMENSION, distance=Distance.COSINE)
            }
        )
        print("[+] Tạo thành công: image_chunks")
    else:
        print("[*] Đã tồn tại: image_chunks")
        
    # 3. Khởi tạo collection Bảng (Dùng 2 vector song song: Caption/Heading và Content thô)
    if not client.collection_exists("table_chunks"):
        client.create_collection(
            collection_name="table_chunks",
            vectors_config={
                "embedding_caption": VectorParams(size=BGE_DIMENSION, distance=Distance.COSINE),
                "embedding_content": VectorParams(size=BGE_DIMENSION, distance=Distance.COSINE)
            }
        )
        print("[+] Tạo thành công: table_chunks")
    else:
        print("[*] Đã tồn tại: table_chunks")
        
    print("--- HOÀN TẤT KHỞI TẠO DATABASE ---")

# CÁC HÀM XỬ LÝ (Dành cho các Tab khác gọi)

def luu_vao_vector_db(client, collection_name, chunk_data):
    """
    Dành cho Docling: Băm dữ liệu nhét vào tủ.
    """
    chunk_id = chunk_data.get("chunk_id")
    
    # Qdrant yêu cầu ID phải là UUID hoặc số nguyên. 
    # Ta dùng hàm băm chuẩn để biến "doc001_chunk014" thành UUID hợp lệ
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))
    
    # Copy dữ liệu để không làm ảnh hưởng bản gốc, sau đó bóc tách vector ra
    payload = chunk_data.copy()
    
    if collection_name == "image_chunks":
        # Ảnh có 2 vector riêng biệt
        vectors = {
            "embedding_caption": payload.pop("embedding_caption", None),
            "embedding_image": payload.pop("embedding_image", None)
        }
    elif collection_name == "table_chunks":
        # Bảng cũng có 2 vector riêng biệt (Dual-Vector)
        vectors = {
            "embedding_caption": payload.pop("embedding_caption", None),
            "embedding_content": payload.pop("embedding_content", None)
        }
    else:
        # Các loại khác chỉ có 1 vector
        vectors = payload.pop("embedding", None)
        
    # Tạo điểm dữ liệu (Phần vector nằm riêng, phần chữ/metadata nằm riêng ở payload)
    point = PointStruct(
        id=point_id,
        vector=vectors,
        payload=payload # Toàn bộ heading_path, content, image_ref... sẽ tự động chui vào đây
    )
    
    # Đẩy lên DB
    client.upsert(
        collection_name=collection_name,
        points=[point]
    )
    return True

def tim_kiem_vector_db(client, collection_name, query_vector, vector_name=None, top_k=3, target_document_id="ALL", page_filter=None):
    """
    Dành cho BGE-M3 / LLM: Bắn vector vào để tìm kiếm.
    - vector_name: Chỉ dùng cho image_chunks (chọn tìm theo "embedding_caption" hay "embedding_image").
    - target_document_id: Tìm theo ID của file cụ thể, "ALL" là tìm trên toàn bộ DB.
    - page_filter: Lọc cứng theo trang (nếu có).
    """
    must_conditions = []
    
    if target_document_id != "ALL":
        must_conditions.append(
            FieldCondition(
                key="document_id",
                match=MatchValue(value=target_document_id)
            )
        )
        
    if page_filter is not None:
        must_conditions.append(
            FieldCondition(
                key="page_number",
                match=MatchValue(value=int(page_filter))
            )
        )

    query_filter = Filter(must=must_conditions) if must_conditions else None

    search_result = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        using=vector_name,
        query_filter=query_filter,
        limit=top_k
    ).points
    
    # Rút trích kết quả sạch sẽ để gửi về cho LLM
    ket_qua = []
    for hit in search_result:
        ket_qua.append({
            "do_chinh_xac": hit.score,
            "du_lieu": hit.payload
        })
    return ket_qua

def dem_va_lay_du_lieu_bang_filter(client, collection_name, target_document_id="ALL", page_filter=None, limit=50):
    """
    Dành cho Analytical RAG (Đếm số lượng / Liệt kê).
    Bypass thuật toán Vector, chỉ sử dụng Filter thuần túy của Qdrant.
    Giới hạn kết quả trả về bằng tham số limit (mặc định 50).
    """
    must_conditions = []
    
    if target_document_id != "ALL":
        must_conditions.append(
            FieldCondition(
                key="document_id",
                match=MatchValue(value=target_document_id)
            )
        )
        
    if page_filter is not None:
        must_conditions.append(
            FieldCondition(
                key="page_number",
                match=MatchValue(value=int(page_filter))
            )
        )
        
    query_filter = Filter(must=must_conditions) if must_conditions else None
    
    # 1. Đếm tổng số lượng chính xác
    count_result = client.count(
        collection_name=collection_name,
        count_filter=query_filter,
        exact=True
    )
    total_count = count_result.count
    
    # 2. Lấy dữ liệu (Payload) giới hạn bằng Scroll
    scroll_result, next_page_offset = client.scroll(
        collection_name=collection_name,
        scroll_filter=query_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False
    )
    
    # Rút trích kết quả
    ket_qua = []
    for point in scroll_result:
        ket_qua.append({
            "do_chinh_xac": 1.0, # Đã match filter thì điểm mặc định là tuyệt đối
            "du_lieu": point.payload
        })
        
    return {
        "count": total_count,
        "items": ket_qua
    }

# CHẠY TEST KHỞI TẠO NẾU GỌI TRỰC TIẾP FILE NÀY
if __name__ == "__main__":
    db_client = get_qdrant_client()
    init_collections(db_client)
