import streamlit as st
import time
import os
import uuid
import firebase_admin
from firebase_admin import credentials, firestore
from supabase import create_client, Client

# 1. KHỞI TẠO KẾT NỐI (Chỉ chạy 1 lần)
@st.cache_resource
def init_connections():
    # Firebase
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except ValueError:
        pass
    db = firestore.client()
    
    # Supabase (BẠN ĐIỀN KEY CỦA BẠN VÀO ĐÂY NHÉ)
    SUPABASE_URL = "https://yrmkrkcnmuqedqboarpe.supabase.co"
    SUPABASE_KEY = "nhap_key_supabase_cua_ban_vao_day"
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    return db, supabase

db, supabase = init_connections()

# 2. CẤU HÌNH GIAO DIỆN STREAMLIT
st.set_page_config(page_title="Agentic RAG System", layout="wide")
st.title("Hệ thống RAG Đa Đại Lý (Agentic RAG)")

# Session State để lưu lịch sử chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# 3. CỘT BÊN TRÁI (SIDEBAR) - NƠI UPLOAD PDF
with st.sidebar:
    st.header("Quản lý Tài liệu")
    uploaded_file = st.file_uploader("Tải lên file PDF", type=["pdf"])
    
    if st.button("Bắt đầu Xử lý"):
        if uploaded_file is not None:
            # Tạo ID duy nhất cho tài liệu
            doc_id = f"doc_{uuid.uuid4().hex[:8]}"
            
            # 1. Lưu tạm file PDF ra máy tính
            local_pdf_path = f"temp_{doc_id}.pdf"
            with open(local_pdf_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            # 2. Bơm file PDF lên Supabase
            with st.spinner("Đang tải PDF lên Supabase..."):
                supabase.storage.from_("rag-data").upload(
                    path=f"{doc_id}.pdf",
                    file=local_pdf_path,
                    file_options={"content-type": "application/pdf"}
                )
                pdf_url = supabase.storage.from_("rag-data").get_public_url(f"{doc_id}.pdf")
            
            # 3. Gửi lệnh lên Firebase để gọi Tab Docling dậy
            db.collection("ui_to_docling_tasks").document(doc_id).set({
                "document_id": doc_id,
                "file_name": uploaded_file.name,
                "pdf_url": pdf_url,
                "status": "pending",
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            
            # 4. Hiển thị thanh trạng thái chờ đợi
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            # Vòng lặp kiểm tra tiến độ từ Firebase
            is_done = False
            timeout_doc = 1800  # Tối đa 30 phút
            count_doc = 0
            while not is_done and count_doc < timeout_doc:
                doc_ref = db.collection("ui_to_docling_tasks").document(doc_id).get()
                if doc_ref.exists:
                    status = doc_ref.to_dict().get("status")
                    
                    if status == "pending":
                        status_text.info("Đang khởi động tiến trình Docling...")
                        progress_bar.progress(10)
                    elif status == "docling_processing":
                        msg = doc_ref.to_dict().get("progress_msg", "Đang phân tích cấu trúc PDF...")
                        status_text.warning(msg)
                        progress_bar.progress(30)
                    elif status == "docling_done":
                        status_text.warning("Phân tích hoàn tất. Đang chuyển sang module Embedding...")
                        progress_bar.progress(50)
                    elif status == "embedding_processing":
                        msg = doc_ref.to_dict().get("progress_msg", "Đang nhúng vector dữ liệu...")
                        status_text.info(msg)
                        progress_bar.progress(65)
                    elif status == "embedding_done":
                        status_text.success("Nhúng vector hoàn tất.")
                        progress_bar.progress(80)
                    elif status == "db_processing":
                        status_text.info("Đang lưu trữ dữ liệu vào Qdrant...")
                        progress_bar.progress(90)
                    elif status == "db_done":
                        status_text.success("Lưu trữ thành công. Hệ thống đã sẵn sàng truy vấn.")
                        progress_bar.progress(100)
                        is_done = True
                    elif status == "error":
                        status_text.error("Hệ thống gặp lỗi trong quá trình xử lý.")
                        is_done = True
                
                if not is_done:
                    time.sleep(10) # 10 giây kiểm tra 1 lần cho file PDF (vì xử lý file lâu)
                    count_doc += 10
            
            if not is_done:
                status_text.error("Quá thời gian chờ xử lý (Timeout). Trạm xử lý tài liệu có thể đã bị treo.")
                
            # Xóa file PDF rác ở máy tính
            if os.path.exists(local_pdf_path):
                os.remove(local_pdf_path)
                
        else:
            st.error("Vui lòng tải lên file PDF trước khi bắt đầu.")

# 4. KHUNG TRUNG TÂM - GIAO DIỆN CHAT AI

# --- KHOANH VÙNG TÌM KIẾM ---
st.markdown("### Cấu hình Truy vấn")
col1, col2 = st.columns([1, 1])

# Lấy danh sách tài liệu đã xử lý xong từ Firebase
@st.cache_data(ttl=60) # Caching kết quả trong 60 giây để tránh sập quota Firebase
def get_document_list():
    docs_ref = db.collection("ui_to_docling_tasks").where(filter=firestore.FieldFilter("status", "==", "db_done")).stream()
    options = {"ALL": "Tất cả tài liệu"}
    for doc in docs_ref:
        data = doc.to_dict()
        options[data["document_id"]] = data.get("file_name", data["document_id"])
    return options

doc_options = get_document_list()

with col1:
    selected_doc_id = st.selectbox(
        "Tài liệu truy vấn:",
        options=list(doc_options.keys()),
        format_func=lambda x: doc_options[x]
    )

with col2:
    st.write("") # Dãn dòng cho cân đối với selectbox
    st.write("")
    trong_pdf = st.checkbox("Sử dụng RAG (Truy xuất tài liệu)", value=True)

st.divider()

# Hiển thị lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("content"):
            st.markdown(msg["content"])
        if msg.get("image_url"):
            st.image(msg["image_url"], width=300)

# Khung nhập câu hỏi (Hỗ trợ kéo thả / Paste ảnh)
if prompt := st.chat_input("Nhập câu hỏi (có thể đính kèm ảnh)...", accept_file=True, file_type=["png", "jpg", "jpeg"]):
    user_text = prompt.text if prompt.text else ""
    uploaded_files = prompt["files"] if "files" in prompt and prompt["files"] else []
    
    co_anh = False
    image_url = None
    
    # 1. Xử lý ảnh đính kèm (nếu có)
    if uploaded_files:
        with st.spinner("Đang tải ảnh lên hệ thống..."):
            img_file = uploaded_files[0]
            img_id = f"chat_img_{uuid.uuid4().hex[:8]}.png"
            local_img_path = f"temp_{img_id}"
            
            with open(local_img_path, "wb") as f:
                f.write(img_file.getbuffer())
                
            supabase.storage.from_("rag-data").upload(
                path=img_id,
                file=local_img_path,
                file_options={"content-type": img_file.type}
            )
            image_url = supabase.storage.from_("rag-data").get_public_url(img_id)
            
            if os.path.exists(local_img_path):
                os.remove(local_img_path)
            co_anh = True

    # 2. Hiện câu hỏi của người dùng
    with st.chat_message("user"):
        if user_text:
            st.markdown(user_text)
        if co_anh:
            st.image(image_url, width=300)
            
    # Lưu vào lịch sử
    st.session_state.messages.append({"role": "user", "content": user_text, "image_url": image_url})
    
    # 3. Gửi lệnh sang Firebase cho Tab LLM
    request_id = f"chat_{uuid.uuid4().hex[:8]}"
    db.collection("ui_to_llm14b_tasks").document(request_id).set({
        "request_id": request_id,
        "query": user_text,
        "trong_pdf": trong_pdf,
        "target_document_id": selected_doc_id, 
        "co_anh": co_anh,
        "image_url": image_url,
        "status": "pending",
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    
    # Hiển thị trạng thái LLM đang xử lý
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Đang phân tích câu hỏi và truy xuất dữ liệu...")
        
        # Vòng lặp chờ đáp án từ LLM
        is_answered = False
        final_answer = ""
        timeout_llm = 900 # Tối đa 15 phút
        count_llm = 0
        
        while not is_answered and count_llm < timeout_llm:
            res_ref = db.collection("llm14b_to_ui_results").document(request_id).get()
            if res_ref.exists:
                res_data = res_ref.to_dict()
                if res_data.get("status") == "done":
                    final_answer = res_data.get("final_answer")
                    is_answered = True
            
            if not is_answered:
                time.sleep(60) # Ngủ 60 giây (1 phút) theo yêu cầu để tiết kiệm Quota tối đa
                count_llm += 60
                
        if not is_answered:
            final_answer = " Xin lỗi, máy chủ LLM phản hồi quá lâu hoặc đã xảy ra lỗi ngầm. Vui lòng kiểm tra lại Terminal của Worker."
            
        # Hiện đáp án thật
        message_placeholder.markdown(final_answer)
        st.session_state.messages.append({"role": "assistant", "content": final_answer})
