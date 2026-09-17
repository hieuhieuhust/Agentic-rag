import time
import requests
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore

# CẤU HÌNH FIREBASE
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except ValueError:
    pass

db = firestore.client()

print(" Đang tải mô hình Qwen VLM (Vision) và Qwen Coder vào VRAM...")
# TODO: Khởi tạo model thật ở đây. Ví dụ: Qwen2-VL-7B-Instruct
print(" Tải xong Qwen Team!")

# HÀM LOGIC AI (VLM VÀ CODER)
def qwen_phan_loai_anh(image_url):
    """
    Qwen VLM (Thị giác) nhìn vào ảnh và phân loại.
    """
    # TODO: Prompt thực tế cho Qwen VLM tải ảnh từ image_url và phân loại 5 nhánh
    # Ở đây giả lập quyết định nhánh dựa vào việc ngẫu nhiên (Hoặc bạn có thể tự chỉnh)
    print(f"  [Qwen VLM] Đang soi ảnh từ: {image_url}")
    
    # Mock kết quả
    loai = "code" # Giả lập phát hiện thấy mã nguồn Python trong ảnh
    loi_giai_thich = "Tôi thấy đây là đoạn mã nguồn. Nó đang định nghĩa một vòng lặp."
    
    return {"loai": loai, "loi_giai_thich_so_bo": loi_giai_thich}

def qwen_coder_giai_thich(image_url, loi_giai_thich_so_bo):
    """
    Qwen Coder (Giải thuật/Toán) phân tích sâu dựa vào gợi ý của VLM.
    """
    print(f"  [Qwen Coder] Đang mổ xẻ mã nguồn/công thức chi tiết...")
    # TODO: Prompt Qwen Coder giải thích rõ Input/Output hoặc viết lại LaTeX
    
    giai_thich_sau = "Đoạn code Python này là thuật toán Sắp xếp nổi bọt (Bubble Sort). Input là mảng số nguyên, Output là mảng đã sắp xếp tăng dần."
    return giai_thich_sau

# LISTENER: HÓNG LỆNH TỪ LLM14B
def on_qwen_task_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED']:
            doc_data = change.document.to_dict()
            doc_id = change.document.id
            
            if doc_data.get("status") == "pending":
                request_id = doc_data.get("request_id")
                image_url = doc_data.get("image_url")
                
                print(f"\n[QWEN TEAM] Nhận task phân tích ảnh từ sếp LLM14b (Req: {request_id})")
                db.collection("llm14b_to_qwen_tasks").document(doc_id).update({"status": "processing"})
                
                try:
                    # BƯỚC 1: Qwen VLM phân loại
                    vlm_result = qwen_phan_loai_anh(image_url)
                    loai = vlm_result["loai"]
                    ket_qua_cuoi = vlm_result["loi_giai_thich_so_bo"]
                    
                    print(f"  -> Qwen VLM phán: Đây là loại '{loai}'")
                    
                    # BƯỚC 2: Rẽ nhánh xử lý sâu (Coder)
                    if loai in ["code", "cong_thuc"]:
                        ket_qua_cuoi = qwen_coder_giai_thich(image_url, vlm_result["loi_giai_thich_so_bo"])
                        print(f"  -> Qwen Coder đã phân tích sâu xong.")
                    
                    # BƯỚC 3: Trả kết quả về cho LLM14b
                    db.collection("qwen_to_llm14b_results").document(f"{request_id}_qwen_result").set({
                        "request_id": request_id,
                        "sub_tracking": doc_data.get("sub_tracking", {}),
                        "qwen_result": {
                            "nguon": "Qwen_Vision_Coder",
                            "loai_anh": loai,
                            "phan_tich": ket_qua_cuoi
                        },
                        "status": "pending",
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                    print("  -> Đã báo cáo kết quả lên bảng 'qwen_to_llm14b_results'.")
                    db.collection("llm14b_to_qwen_tasks").document(doc_id).update({"status": "done"})
                    
                except Exception as e:
                    print(f"[LỖI QWEN TEAM]: {e}")
                    db.collection("llm14b_to_qwen_tasks").document(doc_id).update({"status": "error"})

# CHẠY VÒNG LẶP VÔ HẠN TRÊN COLAB
def start_qwen_worker():
    print(" Bắt đầu khởi động Tab Qwen Team (Worker)...")
    
    qwen_ref = db.collection("llm14b_to_qwen_tasks")
    qwen_watch = qwen_ref.on_snapshot(on_qwen_task_snapshot)
    
    print(" Qwen VLM + Coder đang trực chiến! Chờ ảnh khó từ LLM14b... (Bấm dừng Colab để thoát).")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(" Dừng Tab Qwen Team.")

if __name__ == "__main__":
    start_qwen_worker()

