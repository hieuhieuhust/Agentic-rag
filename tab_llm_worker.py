import time
import uuid
import threading
from collections import deque
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
import PIL.Image
import urllib.request
from io import BytesIO

# CẤU HÌNH FIREBASE VÀ BỘ NHỚ RAM
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except ValueError:
    pass

db = firestore.client()

# CẤU HÌNH API KEYS CHO CÁC MÔ HÌNH (TRẠM CHUYỂN MẠCH)

GOOGLE_API_KEY = ""
GROQ_API_KEY = ""
MISTRAL_API_KEY = ""

OPENAI_API_KEY = "" 
# 

#  CÔNG TẮC: Chọn mô hình muốn dùng để xử lý Text ("LLM", "groq", "mistral", "openai")
ACTIVE_TEXT_PROVIDER = "openai"

# 1. Cấu hình LLM (Dự phòng)
genai.configure(api_key=GOOGLE_API_KEY)
LLM_model = genai.GenerativeModel('LLM-flash-latest') 

# 2. Cấu hình Groq
groq_client = None
if ACTIVE_TEXT_PROVIDER == "groq":
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        pass

# 3. Cấu hình Mistral
mistral_client = None
if ACTIVE_TEXT_PROVIDER == "mistral":
    try:
        from mistralai.client import Mistral
        mistral_client = Mistral(api_key=MISTRAL_API_KEY)
    except ImportError:
        pass

# 4. Cấu hình OpenAI
openai_client = None
if ACTIVE_TEXT_PROVIDER == "openai":
    try:
        import openai
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        print(" Đã kết nối OpenAI API (Sẽ dùng cho cả Text, Vision và Router)!")
    except ImportError:
        print(" Chưa cài thư viện openai. Hãy chạy lệnh: pip install openai")
        ACTIVE_TEXT_PROVIDER = "LLM"

# Bộ nhớ ngắn hạn (RAM) - Lưu tối đa 5 lượt hội thoại gần nhất
conversation_history = deque(maxlen=5)
turn_counter = 0

# Quản lý tiến độ Gom mảnh ghép RAG
active_requests = {}
memory_lock = threading.Lock() 

# HÀM BÁO CÁO TIẾN ĐỘ LÊN UI
def update_llm_progress(doc_id, msg):
    try:
        db.collection("ui_to_llm14b_tasks").document(doc_id).update({"progress_msg": msg})
    except:
        pass

# HÀM LOGIC AI (GỌI MODEL THẬT HOẶC API)
import base64

def pil_to_base64(img):
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def call_llm_with_retry(prompt, is_vision=False, image=None, retries=4, delay=5):
    """
    TRẠM TRUNG CHUYỂN LLM (SWITCHBOARD): Hỗ trợ LLM, Mistral, Groq, và OpenAI
    """
    for attempt in range(retries):
        try:
            if is_vision:
                if ACTIVE_TEXT_PROVIDER == "openai" and openai_client:
                    # Dùng GPT-4o cho Ảnh
                    image_list = image if isinstance(image, list) else [image]
                    content_list = [{"type": "text", "text": prompt}]
                    for img in image_list:
                        b64_str = pil_to_base64(img)
                        data_url = f"data:image/jpeg;base64,{b64_str}"
                        content_list.append({
                            "type": "image_url",
                            "image_url": {"url": data_url}
                        })
                    response = openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": content_list}],
                    )
                    return response.choices[0].message.content
                elif ACTIVE_TEXT_PROVIDER == "mistral" and mistral_client:
                    image_list = image if isinstance(image, list) else [image]
                    content_list = [{"type": "text", "text": prompt}]
                    for img in image_list:
                        b64_str = pil_to_base64(img)
                        data_url = f"data:image/jpeg;base64,{b64_str}"
                        content_list.append({
                            "type": "image_url",
                            "image_url": {"url": data_url} # Mistral pixtral format
                        })
                    response = mistral_client.chat.complete(
                        messages=[{"role": "user", "content": content_list}],
                        model="pixtral-12b-2409", 
                    )
                    return response.choices[0].message.content
                else:
                    if isinstance(image, list):
                        response = LLM_model.generate_content([prompt] + image)
                    else:
                        response = LLM_model.generate_content([prompt, image])
                    return response.text
            else:
                if ACTIVE_TEXT_PROVIDER == "openai" and openai_client:
                    response = openai_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="gpt-4o-mini",
                    )
                    return response.choices[0].message.content
                elif ACTIVE_TEXT_PROVIDER == "groq" and groq_client:
                    response = groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="llama3-8b-8192",
                    )
                    return response.choices[0].message.content
                elif ACTIVE_TEXT_PROVIDER == "mistral" and mistral_client:
                    response = mistral_client.chat.complete(
                        messages=[{"role": "user", "content": prompt}],
                        model="mistral-large-latest", 
                    )
                    return response.choices[0].message.content
                else: 
                    response = LLM_model.generate_content(prompt)
                    return response.text
                    
        except Exception as e:
            print(f"     [Cảnh báo] Lỗi gọi LLM API (Lần thử {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                print(f"     -> Chờ {delay} giây rồi gọi lại...")
                time.sleep(delay)
            else:
                raise e

def tim_kiem_hinh_anh(query: str, page_filter: int = None, is_counting_query: bool = False):
    """Sử dụng khi người dùng muốn tìm kiếm hình ảnh, sơ đồ, biểu đồ."""
    pass

def tim_kiem_bang_bieu(query: str, page_filter: int = None, is_counting_query: bool = False, table_query_type: str = 'semantic'):
    """Sử dụng khi người dùng muốn tìm bảng số liệu. 'table_query_type'='content' nếu hỏi chi tiết số liệu trong bảng, 'semantic' nếu hỏi chung chung."""
    pass

def tim_kiem_cong_thuc(query: str, page_filter: int = None, is_counting_query: bool = False):
    """Sử dụng khi người dùng muốn tìm công thức toán học, vật lý."""
    pass

def tim_kiem_code(query: str, page_filter: int = None, is_counting_query: bool = False):
    """Sử dụng khi người dùng muốn tìm đoạn mã nguồn lập trình."""
    pass

def tim_kiem_van_ban(query: str, page_filter: int = None, is_counting_query: bool = False):
    """Sử dụng khi tìm kiếm văn bản lý thuyết thông thường."""
    pass

def tim_kiem_cau_truc_muc_luc(query: str, page_filter: int = None):
    """Sử dụng khi tìm cấu trúc, mục lục, các chương của tài liệu."""
    pass

TOOL_TO_COLLECTION = {
    "tim_kiem_hinh_anh": "image_chunks",
    "tim_kiem_bang_bieu": "table_chunks",
    "tim_kiem_cong_thuc": "formula_chunks",
    "tim_kiem_code": "code_chunks",
    "tim_kiem_van_ban": "text_chunks",
    "tim_kiem_cau_truc_muc_luc": "intro_and_heading"
}

def llm_dieu_phoi(query, has_image, trong_pdf, image_url=None, history=None):
    """
    TRẠM ĐIỀU PHỐI (Hybrid Agentic Router):
    Sử dụng Native Function Calling (Tools) để tự động chia luồng, gán Tủ, bóc trang và xác định intent cùng lúc.
    """
    print(f"  -> [Trạm Điều Phối] Đang phân tích câu hỏi bằng Agentic Function Calling...")
    
    OPENAI_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "tim_kiem_hinh_anh",
                "description": "Sử dụng khi người dùng muốn tìm kiếm hình ảnh, sơ đồ, biểu đồ.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Câu hỏi viết lại tập trung vào hình ảnh"},
                        "page_filter": {"type": "number", "description": "Số trang nếu có nhắc đến"},
                        "is_counting_query": {"type": "boolean", "description": "Chỉ set True nếu người dùng yêu cầu ĐẾM số lượng (bao nhiêu, how many). Tuyệt đối False nếu hỏi vị trí, ở trang nào."}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "tim_kiem_bang_bieu",
                "description": "Sử dụng khi người dùng muốn tìm bảng số liệu.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "page_filter": {"type": "number"},
                        "is_counting_query": {"type": "boolean", "description": "Chỉ set True nếu người dùng yêu cầu ĐẾM số lượng. Tuyệt đối False nếu hỏi vị trí, ở trang nào."},
                        "table_query_type": {"type": "string", "enum": ["semantic", "content"]}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "tim_kiem_cong_thuc",
                "description": "Sử dụng khi tìm công thức toán học, vật lý.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "page_filter": {"type": "number"},
                        "is_counting_query": {"type": "boolean", "description": "Chỉ set True nếu người dùng yêu cầu ĐẾM số lượng. Tuyệt đối False nếu hỏi vị trí, ở trang nào."}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "tim_kiem_code",
                "description": "Sử dụng khi tìm mã nguồn lập trình.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "page_filter": {"type": "number"},
                        "is_counting_query": {"type": "boolean", "description": "Chỉ set True nếu người dùng yêu cầu ĐẾM số lượng. Tuyệt đối False nếu hỏi vị trí, ở trang nào."}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "tim_kiem_van_ban",
                "description": "Sử dụng khi tìm kiếm văn bản lý thuyết thông thường.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "page_filter": {"type": "number"},
                        "is_counting_query": {"type": "boolean", "description": "Chỉ set True nếu người dùng yêu cầu ĐẾM số lượng. Tuyệt đối False nếu hỏi vị trí, ở trang nào."}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "tim_kiem_cau_truc_muc_luc",
                "description": "Sử dụng khi tìm cấu trúc, mục lục, các chương của tài liệu.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "page_filter": {"type": "number"}
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    try:
        def format_hist(h):
            if not h: return "Không có lịch sử"
            return "\n\n".join([f"User: {t.get('question')}\nAI: {t.get('answer')}" for t in h])

        history_str = ""
        history_str = ""
        if history:
            history_str = f"LỊCH SỬ HỘI THOẠI TRƯỚC ĐÓ:\n{format_hist(history)}\n(Hãy dùng lịch sử này để bổ sung ngữ cảnh, NHƯNG NẾU NGƯỜI DÙNG TẢI LÊN ẢNH MỚI, BẮT BUỘC PHẢI ƯU TIÊN ẢNH MỚI).\n"
            
        warning_str = ""
        if has_image:
            warning_str = "\n[CẢNH BÁO QUAN TRỌNG]: Người dùng có đính kèm một HÌNH ẢNH MỚI trong yêu cầu này. BẠN BẮT BUỘC PHẢI NHÌN VÀO BỨC ẢNH MỚI NHẤT để phân tích nội dung của nó. TUYỆT ĐỐI KHÔNG ĐƯỢC copy kết quả (như 'hoa iris', 'biểu đồ'...) từ Lịch sử trò chuyện nếu nó không khớp với bức ảnh mới! Tự viết lại câu hỏi phụ miêu tả ĐÚNG bức ảnh mới.\n"
            
        prompt = f"""Bạn là Trạm Điều Phối Truy vấn (Router Agent) của hệ thống RAG.
{history_str}
Câu hỏi hiện tại: {query}
{warning_str}
NHIỆM VỤ CỦA BẠN:
1. PHÂN RÃ CÂU HỎI (QUERY DECOMPOSITION): Đọc kỹ câu hỏi, nếu người dùng hỏi về NHIỀU LOẠI đối tượng khác nhau (Ví dụ: Vừa hỏi hình ảnh, Vừa hỏi bảng biểu), BẮT BUỘC bạn phải gọi NHIỀU HÀM TƯƠNG ỨNG cùng lúc (gọi hàm tìm ảnh và hàm tìm bảng). Tuyệt đối KHÔNG ĐƯỢC gộp chung các đối tượng này vào 1 hàm tim_kiem_van_ban duy nhất.
2. VIẾT LẠI CÂU HỎI (REWRITE): Tham số 'query' truyền vào mỗi hàm phải được tách riêng và viết lại sao cho tập trung ĐÚNG vào đối tượng của hàm đó (Ví dụ: Hàm tìm ảnh thì query truyền vào chỉ là 'nội dung hình ảnh', Hàm tìm bảng thì query truyền vào là 'nội dung bảng biểu').
3. BỘ LỌC TRANG: Nếu câu hỏi có nhắc đến số trang cụ thể, BẮT BUỘC phải điền số đó vào tham số 'page_filter' của tất cả các hàm được gọi.

VÍ DỤ TƯ DUY (Hãy học theo cách tư duy này):
- Người dùng hỏi: "có 3 bảng và 2 hình ảnh trong trang 5, tìm nội dung của chúng"
- Tư duy của bạn: 
  + Xác định Elements: Gồm có Bảng biểu (số lượng 3) và Hình ảnh (số lượng 2).
  + Phân rã nhiệm vụ: Cần 2 luồng tìm kiếm độc lập.
  + Hành động: Gọi hàm `tim_kiem_bang_bieu` (query="nội dung của mỗi bảng", page_filter=5.0) VÀ gọi hàm `tim_kiem_hinh_anh` (query="nội dung của mỗi ảnh", page_filter=5.0).
"""
        sub_queries = []

        if ACTIVE_TEXT_PROVIDER == "openai" and openai_client:
            messages = [{"role": "user", "content": prompt}]
            if has_image and image_url:
                req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as url_resp:
                    user_img = PIL.Image.open(BytesIO(url_resp.read())).convert("RGB")
                b64_str = pil_to_base64(user_img)
                messages[0]["content"] = [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"}}
                ]
            
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=OPENAI_TOOLS
            )
            
            if response.choices[0].message.tool_calls:
                import json
                for tool_call in response.choices[0].message.tool_calls:
                    name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except:
                        args = {}
                    
                    if name in TOOL_TO_COLLECTION:
                        sq = {
                            "query": args.get("query", query),
                            "target_collection": TOOL_TO_COLLECTION[name],
                            "page_filter": args.get("page_filter"),
                            "is_counting_query": args.get("is_counting_query", False),
                            "trong_pdf": True,
                            "co_anh": has_image,
                            "image_url": image_url
                        }
                        if name == "tim_kiem_bang_bieu":
                            sq["table_query_type"] = args.get("table_query_type", "semantic")
                        sub_queries.append(sq)
        else:
            # Fallback về LLM
            router_model = genai.GenerativeModel(
                model_name='LLM-flash-latest',
                tools=[tim_kiem_hinh_anh, tim_kiem_bang_bieu, tim_kiem_cong_thuc, tim_kiem_code, tim_kiem_van_ban, tim_kiem_cau_truc_muc_luc]
            )
            if has_image and image_url:
                req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as url_resp:
                    user_img = PIL.Image.open(BytesIO(url_resp.read())).convert("RGB")
                response = router_model.generate_content([prompt, user_img])
            else:
                response = router_model.generate_content(prompt)
                
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        fc = part.function_call
                        name = fc.name
                        args = {}
                        for key, val in fc.args.items():
                            args[key] = val
                        
                        if name in TOOL_TO_COLLECTION:
                            sq = {
                                "query": args.get("query", query),
                                "target_collection": TOOL_TO_COLLECTION[name],
                                "page_filter": args.get("page_filter"),
                                "is_counting_query": args.get("is_counting_query", False),
                                "trong_pdf": True,
                                "co_anh": has_image,
                                "image_url": image_url
                            }
                            if name == "tim_kiem_bang_bieu":
                                sq["table_query_type"] = args.get("table_query_type", "semantic")
                            sub_queries.append(sq)
        
        if len(sub_queries) > 0:
            print(f"  -> [Trạm Điều Phối] Xong! LLM đã phân rã thành {len(sub_queries)} chặng (Tools).")
            for i, sq in enumerate(sub_queries):
                if has_image and sq.get("target_collection") == "image_chunks":
                    print(f"     + Lệnh {i+1}: [BƯỚC 1 - TÌM MỎ NEO] Dùng Ảnh vật lý đính kèm đưa cho SigLIP để định vị điểm neo tuyệt đối trong tủ 'image_chunks'")
                    print(f"       (Câu hỏi phụ do LLM dịch ra để hỗ trợ: '{sq['query']}')")
                else:
                    print(f"     + Lệnh {i+1}: Câu hỏi phụ='{sq['query']}', Tủ={sq['target_collection']}, Trang={sq.get('page_filter')}, Đếm={sq.get('is_counting_query')}")
            return sub_queries
            
    except Exception as e:
        print(f"  -> Lỗi Điều phối Agentic: {e}. Fallback về mặc định.")

    return [
        {"query": query, "trong_pdf": True, "co_anh": has_image, "target_collection": "image_chunks" if has_image else "text_chunks", "image_url": image_url, "page_filter": None, "is_counting_query": False}
    ]

def phan_loai_noi_dung(original_query, sub_queries, history=None):
    """Phân loại xem câu hỏi là 'nội dung chung chung' (generic) hay 'nội dung cụ thể' (specific).
    - Generic: 'nội dung của chúng là gì?', 'hình ảnh trang 25 nói về gì?' -> Lấy hết từ DB, không cần vector search.
    - Specific: 'tìm bảng biểu về GDP', 'hình ảnh mô tả kiến trúc mạng' -> Tìm bằng vector search bình thường.
    """
    # Chỉ xử lý các sub_query KHÔNG phải counting (counting đã có đường riêng)
    non_counting = [sq for sq in sub_queries if not sq.get("is_counting_query", False)]
    if not non_counting:
        return sub_queries
    
    # Chỉ cần phân loại khi có page_filter (vì fetch_all chỉ hợp lý khi biết trang cụ thể)
    has_page = any(sq.get("page_filter") is not None for sq in non_counting)
    if not has_page:
        return sub_queries
    
    def format_hist(h):
        if not h: return "Không có lịch sử"
        return "\n".join([f"User: {t.get('question')}\nAI: {t.get('answer')}" for t in h[-3:]])
    
    prompt = f"""Phân loại câu hỏi sau vào 1 trong 2 loại:

Lịch sử trò chuyện:
{format_hist(history)}

Câu hỏi: {original_query}

- "GENERIC": Câu hỏi CHUNG CHUNG, không nêu nội dung cụ thể. Ví dụ: "nội dung của chúng là gì?", "hình ảnh đó nói về gì?", "mô tả các bảng biểu", "trang 25 có gì?".
- "SPECIFIC": Câu hỏi CÓ MÔ TẢ nội dung cụ thể để tìm kiếm. Ví dụ: "tìm bảng về GDP", "hình ảnh kiến trúc mạng neural", "công thức tính lực ma sát".

CHỈ TRẢ VỀ 1 TỪ: "GENERIC" hoặc "SPECIFIC"."""
    
    try:
        res = call_llm_with_retry(prompt).strip().upper()
        if "GENERIC" in res:
            print(f"  -> [Phân Loại Nội Dung] Câu hỏi CHUNG CHUNG → Đi tắt lấy hết từ DB (không cần vector search).")
            for sq in sub_queries:
                if not sq.get("is_counting_query", False) and sq.get("page_filter") is not None:
                    sq["is_fetch_all_content"] = True
        else:
            print(f"  -> [Phân Loại Nội Dung] Câu hỏi CỤ THỂ → Tìm bằng vector search bình thường.")
    except Exception as e:
        print(f"  -> [Phân Loại Nội Dung] Lỗi: {e}. Mặc định: SPECIFIC.")
    
    return sub_queries

def llm_loc_text_quanh_anh(caption, prev_text, next_text):
    """Sử dụng LLM Text để xem đoạn văn bản nào thật sự liên quan đến Đối tượng (Ảnh, Bảng, Code)."""
    if not prev_text and not next_text:
        return ""
        
    prompt = f"""Bạn là biên tập viên dữ liệu. 
Dưới đây là thông tin/chú thích của một đối tượng (Ảnh/Bảng/Code):
"{caption}"

Đoạn văn bản PHÍA TRƯỚC đối tượng: 
"{prev_text}"

Đoạn văn bản PHÍA SAU đối tượng: 
"{next_text}"

Nhiệm vụ: Đoạn văn bản nào giải thích/liên quan trực tiếp tới nội dung của đối tượng hơn?
- Nếu cả 2 đều liên quan, hãy gộp cả 2 lại.
- Nếu chỉ 1 đoạn liên quan, hãy trả về đoạn đó, bỏ đoạn kia.
- Nếu không đoạn nào liên quan, hãy trả về rỗng.

CHỈ TRẢ VỀ ĐOẠN VĂN BẢN ĐÃ ĐƯỢC CHỌN, KHÔNG GIẢI THÍCH GÌ THÊM.
"""
    try:
        print("     -> Đang dùng Text LLM (Chi phí thấp) để thanh lọc ngữ cảnh quanh ảnh...")
        res = call_llm_with_retry(prompt)
        return res.strip()
    except Exception as e:
        print(f"     [Lỗi] Lỗi khi thanh lọc text quanh ảnh: {e}")
        return f"{prev_text} {next_text}"

def llm_tuyen_chon_chang_1(original_query, multimodal_chunks, history=None):
    """CHẶNG 1 MỚI: Tuyển chọn các đối tượng đa phương tiện bằng LLM (đánh giá hàng loạt trong 1 prompt).
    - Lọc sơ bộ: Score < 30% bị loại, giữ tối đa 5 ứng viên.
    - LLM đánh giá caption/content của từng ứng viên so với câu hỏi.
    - Trả về danh sách các đối tượng được duyệt.
    """
    # Bước 1: Lọc sơ bộ bằng ngưỡng Vector Score
    MIN_SCORE = 0.30
    MAX_CANDIDATES = 5
    
    candidates = [c for c in multimodal_chunks if c.get("do_chinh_xac", 0) >= MIN_SCORE]
    candidates = sorted(candidates, key=lambda x: x.get("do_chinh_xac", 0), reverse=True)[:MAX_CANDIDATES]
    
    if not candidates:
        print("  -> Không có đối tượng nào đạt ngưỡng 30%. Bỏ qua Multi-hop.")
        return []
    
    if len(candidates) == 1:
        print(f"  -> Chỉ có 1 ứng viên (Score: {candidates[0].get('do_chinh_xac', 0)*100:.1f}%). Tự động duyệt.")
        return candidates
    
    # Bước 2: Chuẩn bị prompt đánh giá hàng loạt
    def format_hist(h):
        if not h: return "Không có lịch sử"
        return "\n".join([f"User: {t.get('question')}\nAI: {t.get('answer')}" for t in h[-2:]])
    
    descriptions = []
    for i, chunk in enumerate(candidates):
        payload = chunk.get("du_lieu", {})
        score = chunk.get("do_chinh_xac", 0)
        # Lấy caption và content (có gì lấy nấy)
        caption = payload.get("caption", "")
        content = payload.get("markdown") or payload.get("html") or payload.get("csv") or payload.get("content") or ""
        page = payload.get("page_number", "?")
        
        desc_parts = []
        if caption: desc_parts.append(f"Caption: {caption[:200]}")
        if content and content != caption: desc_parts.append(f"Content: {content[:300]}")
        if not desc_parts: desc_parts.append("Không có thông tin mô tả")
        
        descriptions.append(f"[{i+1}] (Trang {page}, Score: {score*100:.1f}%)\n" + "\n".join(desc_parts))
    
    all_desc = "\n---\n".join(descriptions)
    
    prompt = f"""Bạn là Thẩm định viên AI. Hãy đánh giá xem các đối tượng dưới đây có LIÊN QUAN đến câu hỏi của người dùng hay không.

Lịch sử trò chuyện (để hiểu đại từ "nó", "chúng"):
{format_hist(history)}

Câu hỏi: {original_query}

Danh sách ứng viên:
{all_desc}

Nhiệm vụ: Với MỖI ứng viên, hãy đánh giá xem nội dung/chú thích của nó có TƯƠNG ĐỐI liên quan đến câu hỏi không (không cần khớp 100%, chỉ cần có phần liên quan là được).
Trả về ĐÚNG danh sách số thứ tự các ứng viên nên GIỮ, cách nhau bằng dấu phẩy.
Ví dụ: "1,3" hoặc "1,2,3,4" hoặc "2".
Nếu KHÔNG có ứng viên nào liên quan, trả về "NONE".
CHỈ TRẢ VỀ SỐ, KHÔNG GIẢI THÍCH."""

    try:
        print(f"  -> [Tuyển Chọn Chặng 1] Đang để LLM đánh giá {len(candidates)} ứng viên (Score >= 30%)...")
        res = call_llm_with_retry(prompt).strip().upper()
        
        if "NONE" in res:
            print("  -> LLM đánh giá: Không có ứng viên nào liên quan.")
            return []
        
        # Parse kết quả: lấy các số từ response
        import re
        selected_indices = [int(x) for x in re.findall(r'\d+', res)]
        selected = []
        for idx in selected_indices:
            if 1 <= idx <= len(candidates):
                selected.append(candidates[idx - 1])
        
        print(f"  -> LLM đã duyệt {len(selected)}/{len(candidates)} đối tượng: {[i for i in selected_indices if 1 <= i <= len(candidates)]}")
        return selected
    except Exception as e:
        print(f"  -> Lỗi tuyển chọn: {e}. Fallback: Giữ tất cả ứng viên.")
        return candidates

def get_core_info_for_chunk(payload, original_content=""):
    """
    Hàm hỗ trợ lấy thông tin cốt lõi của một đối tượng, đặc biệt xử lý riêng cho Bảng biểu:
    Gộp Caption + Table_Horizontal_Text (hoặc Markdown) để tăng độ chính xác khi truy vấn.
    """
    caption_text = str(payload.get("caption") or "").strip()
    if caption_text.lower() == "none":
        caption_text = ""
        
    if "table_horizontal_text" in payload or "markdown" in payload:
        # Xử lý cho bảng biểu: Gộp caption và nội dung bảng
        table_text = str(payload.get("table_horizontal_text") or payload.get("markdown") or "").strip()
        core_info = f"{caption_text}\n{table_text}".strip()
    else:
        # Xử lý cho hình ảnh hoặc các đối tượng khác
        core_info = caption_text or payload.get("html") or payload.get("csv") or payload.get("latex") or payload.get("code_raw") or original_content or payload.get("content") or ""
        
    return core_info.strip()

def llm_tao_truy_van_mo_rong_v2(selected_chunks, is_fetch_all=False):
    """CHẶNG 2 MỚI: Tạo truy vấn mở rộng cho TẤT CẢ đối tượng đã được duyệt.
    Luôn sử dụng core_info (đặc biệt là Bảng thì dùng Caption + Nội dung) để làm truy vấn.
    """
    expansion_queries = []
    for i, chunk in enumerate(selected_chunks):
        payload = chunk.get("du_lieu", {})
        
        # Lấy thông tin cốt lõi của đối tượng (đã ghép caption + table text cho bảng)
        core_info = get_core_info_for_chunk(payload)
        
        # Nếu core_info rỗng (thường là do DB thiếu key), hoặc chứa chuỗi báo lỗi, ép kiểu sang text để có cái tìm kiếm
        if not core_info or str(core_info).strip() == "" or "Không có thông tin cốt lõi" in str(core_info):
            core_info = f"thông tin đối tượng trang {payload.get('page_number', '')}"
            
        # Dùng core_info (đã chứa nội dung đầy đủ của ảnh/bảng) làm truy vấn chính
        context_text = core_info
        
        if context_text:
            expansion_queries.append({
                "query": context_text[:300],  # Giới hạn độ dài truy vấn
                "target_collection": "text_chunks",
                "source_chunk_index": i  # Để biết kết quả này thuộc về đối tượng nào
            })
    
    return expansion_queries

def llm_loc_text_vong_2(caption, stage_2_results):
    """Dùng LLM xác định xem các đoạn text chặng 2 có liên quan tới caption không."""
    if not stage_2_results:
        return []
        
    kept_results = []
    print(f"  -> Đang chấm điểm {len(stage_2_results)} mảnh ghép Chặng 2 xem có liên quan tới Caption không...")
    
    for res in stage_2_results:
        payload = res.get("du_lieu", {})
        content = payload.get("content", str(payload))
        
        prompt = f"""Bạn là Thẩm định viên dữ liệu.
Chú thích ảnh (Caption): "{caption}"
Đoạn văn bản cần kiểm tra: "{content}"

Nhiệm vụ: Đoạn văn bản này CÓ LIÊN QUAN mật thiết đến nội dung của Chú thích ảnh không?
Chỉ trả lời ĐÚNG 1 TỪ: "CO" hoặc "KHONG".
"""
        try:
            eval_res = call_llm_with_retry(prompt).strip().upper()
            if "CO" in eval_res:
                kept_results.append(res)
        except Exception as e:
            print(f"     [Lỗi lọc chặng 2]: {e}")
            
    print(f"  -> Đã giữ lại {len(kept_results)}/{len(stage_2_results)} mảnh ghép liên quan.")
    return kept_results

def kiem_tra_y_dinh(original_query):
    print(f"  -> Đang kiểm tra xem câu hỏi có cần lôi PDF ra không...")
    prompt = f"""Hãy xác định xem câu hỏi sau có cần tìm kiếm trong tài liệu chuyên môn (PDF) không, hay chỉ là câu hỏi phiếm thông thường (chào hỏi, tán gẫu, hỏi ngày tháng...).
    
Câu hỏi: {original_query}

Chỉ trả về ĐÚNG 1 từ khóa:
- Ghi "RAG" nếu câu hỏi cần lục tìm tài liệu.
- Ghi "CHAT" nếu là câu hỏi phiếm/thông thường.
"""
    try:
        res = call_llm_with_retry(prompt)
        res = res.strip().upper()
        if "CHAT" in res: return "CHAT"
        return "RAG"
    except Exception:
        return "RAG" # Fallback an toàn

def llm_tra_loi_truc_tiep_voi_text(original_query, history):
    print(f"  -> Câu hỏi giao tiếp thông thường. LLM tự trả lời không cần RAG...")
    
    def format_hist(h):
        if not h: return "Không có lịch sử"
        return "\n\n".join([f"User: {t.get('question')}\nAI: {t.get('answer')}" for t in h])

    prompt = f"""Bạn là trợ lý AI thông minh thân thiện. Hãy trả lời câu hỏi của người dùng.
    
Lịch sử trò chuyện:
{format_hist(history)}

Câu hỏi: {original_query}
"""
    try:
        res = call_llm_with_retry(prompt)
        return res
    except Exception as e:
        print(f"[Lỗi LLM API]: {e}")
        return "Xin lỗi, tổng đài Google LLM đang bận do quá nhiều yêu cầu cùng lúc. Bạn đợi vài giây rồi hỏi lại nhé!"

def llm_tra_loi_truc_tiep_voi_anh(original_query, image_url, history):
    print(f"  -> Đang tải ảnh từ {image_url} để LLM tự xử lý...")
    
    def format_hist(h):
        if not h: return "Không có lịch sử"
        return "\n\n".join([f"User: {t.get('question')}\nAI: {t.get('answer')}" for t in h])

    try:
        req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as url_resp:
            img_data = url_resp.read()
        img = PIL.Image.open(BytesIO(img_data))
        
        prompt = f"""Đây là một bức ảnh được cung cấp trực tiếp.
Hãy trả lời câu hỏi của người dùng dựa trên bức ảnh này.

Lịch sử trò chuyện gần nhất:
{format_hist(history)}

Câu hỏi: {original_query}
"""
        res = call_llm_with_retry(prompt, is_vision=True, image=img)
        return res
    except Exception as e:
        print(f"[Lỗi xử lý ảnh với LLM]: {e}")
        return "Xin lỗi, mạng quá tải, không thể phân tích bức ảnh này bằng LLM lúc này."

def llm_tu_kiem_tra(original_query, gathered_results, history=None):
    formatted_contexts = []
    for i, res in enumerate(gathered_results):
        if isinstance(res, dict) and "du_lieu" in res:
            payload = res.get("du_lieu", {})
            content = payload.get("content", str(payload))
            page = payload.get("page_number", payload.get("page", "Không rõ"))
            doc_id = payload.get("document_id", "Không rõ")
            formatted_contexts.append(f"--- Nguồn {i+1} (File: {doc_id} | Trang: {page}) ---\n{content}")
        else:
            formatted_contexts.append(f"--- Nguồn {i+1} ---\n{str(res)}")
    context_str = "\n".join(formatted_contexts)
    
    def format_hist(h):
        if not h: return "Không có lịch sử"
        return "\n".join([f"User: {t.get('question')}\nAI: {t.get('answer')}" for t in h[-2:]])
        
    hist_str = format_hist(history)
    
    prompt = f"""Bạn là một Thẩm định viên AI.
Nhiệm vụ: Đối chiếu Yêu cầu của câu hỏi với Nội dung trích xuất được. Hãy xác định xem nội dung này ĐÃ ĐÚNG VÀ ĐỦ để giải quyết triệt để yêu cầu của câu hỏi chưa?

Lịch sử trò chuyện gần đây (để hiểu các đại từ như "nó", "chúng"):
{hist_str}

Câu hỏi / Yêu cầu gốc: {original_query}

Thông tin trích xuất tìm được:
{context_str}

Chỉ trả về ĐÚNG 1 từ khóa:
- "DU_THONG_TIN" nếu các thông tin này đã đánh trúng và đủ giải quyết yêu cầu.
- "THIEU_THONG_TIN" nếu nội dung lạc đề, thiếu chủ thể, hoặc không giải quyết được yêu cầu gốc.
"""
    try:
        print("  -> Đang tự đánh giá xem mảnh ghép đã giải quyết đúng yêu cầu câu hỏi chưa...")
        res = call_llm_with_retry(prompt)
        res = res.strip().upper()
        if "THIEU_THONG_TIN" in res:
            print("  ->  Đánh giá: THIẾU THÔNG TIN! Cần tìm kiếm lại.")
            return {"status": "THIEU_THONG_TIN"}
        print("  ->  Đánh giá: ĐỦ THÔNG TIN.")
        return {"status": "DU_THONG_TIN"}
    except Exception as e:
        print(f"  -> Lỗi khi tự đánh giá: {e}. Fallback: Cho qua (DU_THONG_TIN).")
        return {"status": "DU_THONG_TIN"}

def llm_loc_anh(user_image_url, gathered_results):
    print("  -> Đang dùng LLM để đối chiếu hình ảnh tải lên và hình tìm được...")
    # Tải ảnh user
    try:
        req = urllib.request.Request(user_image_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as url_resp:
            user_img = PIL.Image.open(BytesIO(url_resp.read())).convert("RGB")
    except Exception as e:
        print(f"     [Lỗi] Không tải được ảnh của user: {e}. Bỏ qua bước lọc.")
        return gathered_results
        
    filtered_results = []
    for res in gathered_results:
        if not isinstance(res, dict) or "du_lieu" not in res:
            filtered_results.append(res)
            continue
            
        payload = res.get("du_lieu", {})
        img_url = payload.get("image_url") or payload.get("image_ref")
        
        # Chỉ xét duyệt những kết quả RAG có chứa ảnh
        if img_url:
            try:
                print("     -> Đang kiểm tra 1 ảnh từ Database bằng Mắt thần...")
                req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as url_resp:
                    retrieved_img = PIL.Image.open(BytesIO(url_resp.read())).convert("RGB")
                    
                prompt = """Bạn là Thẩm định viên hình ảnh.
Ảnh 1: Ảnh do người dùng cung cấp.
Ảnh 2: Ảnh tìm được từ hệ thống.

Nhiệm vụ: Hai ảnh này có CHUNG MỘT ĐỐI TƯỢNG, NỘI DUNG hoặc LÀ CÙNG MỘT BỨC ẢNH (có thể khác nhau về độ phân giải, màu sắc, hoặc bị cắt viền đôi chút) không?
Chỉ trả về ĐÚNG 1 từ khóa:
- Ghi "GIONG_NHAU" nếu 2 ảnh chứa cùng nội dung cần tìm.
- Ghi "KHAC_NHAU" nếu nội dung hoàn toàn không liên quan.
"""
                eval_res = call_llm_with_retry(prompt, is_vision=True, image=[user_img, retrieved_img]).strip().upper()
                if "KHAC_NHAU" in eval_res:
                    print("      Loại bỏ: Ảnh tìm được không khớp với ảnh của người dùng.")
                    continue
                else:
                    print("      Giữ lại: Ảnh tìm được khớp với ảnh người dùng!")
            except Exception as e:
                print(f"     [Lỗi] Lỗi khi so sánh ảnh: {e}")
        
        filtered_results.append(res)
    return filtered_results

def llm_tong_hop_dap_an(original_query, gathered_results, history, is_counting_query=False, total_count=0):
    # 1. Gom nội dung các mảnh ghép thành Context đưa cho LLM
    formatted_contexts = []
    images = []
    
    def format_hist(h):
        if not h: return "Không có lịch sử"
        return "\n\n".join([f"User: {t.get('question')}\nAI: {t.get('answer')}" for t in h])
    
    for i, res in enumerate(gathered_results):
        if isinstance(res, dict) and "du_lieu" in res:
            payload = res.get("du_lieu", {})
            content = payload.get("content", "")
            
            # Xử lý riêng nếu mảnh ghép là Ảnh
            img_url = payload.get("image_url") or payload.get("image_ref")
            if img_url:
                caption = payload.get("caption", "")
                if caption is None or str(caption).strip().lower() == "none":
                    caption = "Không có chú thích"
                prev_text = payload.get("prev_text_snippet", "Không có")
                next_text = payload.get("next_text_snippet", "Không có")
                # Ghi đè content để prompt LLM tốt hơn
                content = f"{content}\n[ĐÂY LÀ MỘT BỨC ẢNH CÓ THẬT TRONG TÀI LIỆU]\nChú thích ảnh: {caption}\nNgữ cảnh trước ảnh: {prev_text}\nNgữ cảnh sau ảnh: {next_text}"
                
                # Tải ảnh từ Supabase/Firebase để LLM nhìn thấy (CẤM TẢI NẾU LÀ LỆNH ĐẾM)
                if not is_counting_query:
                    try:
                        req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req) as url_resp:
                            img_data = url_resp.read()
                        img = PIL.Image.open(BytesIO(img_data)).convert("RGB")
                        images.append(img)
                    except Exception as e:
                        print(f"  -> Lỗi tải ảnh ghép cho LLM: {e}")
            elif not content:
                content = str(payload)
                
            page = payload.get("page_number", payload.get("page", "Không rõ"))
            doc_id = payload.get("document_id", "Không rõ")
            score = res.get("do_chinh_xac", 0)
            
            # Đọc thẻ nhãn xuất xứ
            sub_query_text = res.get("_sub_query_tag", "Không rõ")
            target_col = res.get("_target_collection_tag", "Unknown")
            collection_name_map = {
                "image_chunks": "Hình ảnh/Biểu đồ",
                "table_chunks": "Bảng biểu",
                "text_chunks": "Văn bản",
                "formula_chunks": "Công thức",
                "code_chunks": "Mã nguồn",
                "toc_chunks": "Mục lục"
            }
            collection_vn = collection_name_map.get(target_col, target_col)
            
            formatted_contexts.append(f"--- Nguồn {i+1} | Tủ dữ liệu: {collection_vn} | Mục đích tìm kiếm: \"{sub_query_text}\" (Độ khớp: {score*100:.1f}%) ---\nFile: {doc_id} | Trang: {page}\nNội dung: {content}")
        elif isinstance(res, dict) and res.get("nguon") == "Qwen_Vision_Coder":
            loai = res.get("loai_anh", "Không rõ")
            phan_tich = res.get("phan_tich", "")
            formatted_contexts.append(f"--- Báo cáo từ Chuyên gia Qwen (Phân tích ảnh tải lên) ---\nLoại ảnh: {loai}\nNội dung chi tiết: {phan_tich}")
        else:
            formatted_contexts.append(f"--- Nguồn {i+1} ---\nNội dung: {str(res)}")
            
    context_str = "\n\n".join(formatted_contexts)
    
    # 2. Xây dựng Prompt ra lệnh cho LLM
    if is_counting_query:
        prompt = f"""Bạn là trợ lý AI thông minh. 
Nhiệm vụ của bạn là trả lời câu hỏi ĐẾM SỐ LƯỢNG của người dùng.

HỆ THỐNG ĐÃ TÌM VÀ ĐẾM ĐƯỢC CHÍNH XÁC: {total_count} KẾT QUẢ.
YÊU CẦU BẮT BUỘC: 
- CHỈ thông báo tổng số lượng này một cách ngắn gọn.
- Có thể liệt kê tên các đối tượng tiêu biểu (nếu có trong dữ liệu).
- TUYỆT ĐỐI KHÔNG miêu tả dài dòng, KHÔNG phân tích chi tiết nội dung bức ảnh hay bảng biểu.

TÀI LIỆU CUNG CẤP:
{context_str}

LỊCH SỬ TRÒ CHUYỆN GẦN NHẤT:
{history}

CÂU HỎI CỦA NGƯỜI DÙNG: {original_query}
"""
    else:
        prompt = f"""Bạn là trợ lý AI thông minh chuyên phân tích tài liệu (RAG). 
Hãy trả lời câu hỏi của người dùng dựa CHỈ vào các thông tin dưới đây.

ĐIỀU KIỆN BẮT BUỘC: 
- CỰC KỲ NGẮN GỌN, xúc tích, đi thẳng vào vấn đề.
- Bạn PHẢI trích dẫn nguồn cho mỗi lập luận.
- Định dạng trích dẫn ở cuối câu/đoạn PHẢI ghi rõ Tên File, Số Trang và Độ khớp Vector. Ví dụ: (Trích: Trang 15, Độ khớp: 89.5%).
- Nếu trong tài liệu không chứa câu trả lời, hãy nói rằng tài liệu không đề cập.

TÀI LIỆU CUNG CẤP:
{context_str}

LỊCH SỬ TRÒ CHUYỆN GẦN NHẤT:
{history}

CÂU HỎI CỦA NGƯỜI DÙNG: {original_query}
"""
    
    print(f"  -> Đang gửi mớ bòng bong (kèm {len(images)} ảnh) lên Google LLM để tổng hợp...")
    try:
        if len(images) > 0:
            # Gửi cả Text và Ảnh (Dùng Multimodal RAG qua Switchboard)
            res = call_llm_with_retry(prompt, is_vision=True, image=images)
            return res
        else:
            res = call_llm_with_retry(prompt)
            return res
    except Exception as e:
        print(f"[Lỗi gọi LLM API]: {e}")
        return "Xin lỗi, tổng đài Google LLM đang bận do quá tải. Không thể tổng hợp đáp án lúc này, bạn đợi 10 giây rồi thử lại nha!"

# LISTENER 1: NHẬN CÂU HỎI TỪ GIAO DIỆN (UI) -> TÁCH VÀ GỬI ĐI
def on_ui_chat_snapshot(col_snapshot, changes, read_time):
    global turn_counter
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED']:
            doc_data = change.document.to_dict()
            doc_id = change.document.id
            
            if doc_data.get("status") == "pending":
                original_query = doc_data.get("query")
                has_image = doc_data.get("co_anh", False)
                trong_pdf = doc_data.get("trong_pdf", True)
                image_url = doc_data.get("image_url", None)
                target_document_id = doc_data.get("target_document_id", "ALL")
                
                request_id = f"req_{uuid.uuid4().hex[:8]}" 
                turn_counter += 1
                
                print(f"\n[LLM] Phiên hỏi {request_id} | '{original_query}' | Tệp đích: {target_document_id} | Trong PDF: {trong_pdf}")
                db.collection("ui_to_llm14b_tasks").document(doc_id).update({"status": "processing"})
                update_llm_progress(doc_id, "Đang phân tích ý định câu hỏi...")
                
                try:
                    # TỰ ĐỘNG PHÁT HIỆN Ý ĐỊNH NẾU LÀ CÂU HỎI TEXT
                    if trong_pdf and not has_image:
                        y_dinh = kiem_tra_y_dinh(original_query)
                        if y_dinh == "CHAT":
                            print(f"  ->  AI kết luận: Đây là câu hỏi phiếm, TỰ ĐỘNG BỎ QUA PDF!")
                            trong_pdf = False

                    send_to_qwen = False
                    sub_queries = []
                    
                    # RẼ NHÁNH TỐI GIẢN: Xử lý các trường hợp không dùng PDF
                    if not trong_pdf:
                        if has_image:
                            print(f"  -> Ảnh ngoại lai. Giao cho Đội Qwen phân tích độc lập...")
                            update_llm_progress(doc_id, "Câu hỏi không dùng PDF. Đang gọi biệt đội Qwen phân tích ảnh...")
                            send_to_qwen = True
                            # Không continue, để luồng Async phía dưới tạo task cho Qwen
                        else:
                            print(f"  -> Chat thông thường. LLM trả lời trực tiếp...")
                            update_llm_progress(doc_id, "Đang suy nghĩ (Chat thông thường)...")
                            final_answer = llm_tra_loi_truc_tiep_voi_text(original_query, list(conversation_history))
                            
                            conversation_history.append({
                                "turn_index": turn_counter,
                                "question": original_query,
                                "answer": final_answer
                            })
                            
                            db.collection("llm14b_to_ui_results").document(doc_id).set({
                                "request_id": request_id,
                                "final_answer": final_answer,
                                "status": "done",
                                "timestamp": firestore.SERVER_TIMESTAMP
                            })
                            print(f" ĐÃ GỬI ĐÁP ÁN CHO UI (Chat thường, không qua RAG).")
                            continue # Bỏ qua luồng Async bên dưới
                    else:
                        # 1. Trạm Lễ Tân (Router): Tách câu hỏi và Phân luồng RAG
                        update_llm_progress(doc_id, "Trạm Điều Phối đang dùng Tools gán nhãn Tủ đích...")
                        sub_queries = llm_dieu_phoi(original_query, has_image, trong_pdf, image_url, history=list(conversation_history))
                        # Phân loại: câu hỏi chung chung (lấy hết) vs câu hỏi cụ thể (vector search)
                        sub_queries = phan_loai_noi_dung(original_query, sub_queries, history=list(conversation_history))
                        
                        # THEO YÊU CẦU: Trong PDF thì KHÔNG đẩy sang Qwen
                        send_to_qwen = False
                        
                    total_subs = len(sub_queries) + (1 if send_to_qwen else 0)
                    
                    with memory_lock:
                        active_requests[request_id] = {
                            "ui_doc_id": doc_id,
                            "original_query": original_query,
                            "total_subs": total_subs,
                            "received_subs": 0,
                            "sub_results": [],
                            "loop_count": 0,
                            "co_anh": has_image,
                            "image_url": image_url,
                            "is_counting_query": any(sq.get("is_counting_query", False) for sq in sub_queries),
                            "is_fetch_all_content": any(sq.get("is_fetch_all_content", False) for sq in sub_queries),
                            "history": list(conversation_history),
                            "stage": 1 # Khởi đầu ở Chặng 1
                        }
                        
                    # 2. Phân phát lệnh cho Embedding
                    update_llm_progress(doc_id, f"Bắn {len(sub_queries)} lệnh vào Qdrant để lùng sục...")
                    for idx, sq in enumerate(sub_queries):
                        sub_index = idx + 1
                        
                        # Fix: Đảm bảo nhồi ảnh của user vào query nếu Tủ đích là ảnh
                        q_img_url = sq.get("image_url")
                        if not q_img_url and has_image and sq.get("target_collection") == "image_chunks":
                            q_img_url = image_url
                        is_counting_query = sq.get("is_counting_query", False)
                        
                        task_data = {
                            "request_id": request_id,
                            "query": sq["query"],
                            "query_image_url": q_img_url, # Dùng cho SigLIP tìm ảnh
                            "trong_pdf": sq.get("trong_pdf", True),
                            "target_collection": sq.get("target_collection"),
                            "target_document_id": target_document_id, # Đẩy cờ đi tiếp
                            "page_filter": sq.get("page_filter"), # Cờ lọc cứng theo trang (nếu có)
                            "table_query_type": sq.get("table_query_type"), # Thêm cờ cho Bảng
                            "is_counting_query": is_counting_query, # Cờ đếm/liệt kê
                            "sub_tracking": {"sub_index": sub_index, "total_subs": total_subs, "sub_query": sq["query"]},
                            "status": "pending",
                            "timestamp": firestore.SERVER_TIMESTAMP
                        }

                        is_fetch_all = sq.get("is_fetch_all_content", False)
                        
                        if is_counting_query:
                            print(f"  -> [ANALYTICAL RAG] Đi tắt thẳng sang Trạm DB (ĐẾM): {sq['query']} (Tủ: {sq['target_collection']})")
                            db.collection("embedding_to_db_tasks").document(f"{request_id}_sub{sub_index}").set(task_data)
                        elif is_fetch_all:
                            task_data["is_fetch_all_content"] = True
                            print(f"  -> [FETCH ALL] Đi tắt thẳng sang Trạm DB (LẤY HẾT NỘI DUNG): {sq['query']} (Tủ: {sq['target_collection']}, Trang: {sq.get('page_filter')})")
                            db.collection("embedding_to_db_tasks").document(f"{request_id}_sub{sub_index}").set(task_data)
                        else:
                            if q_img_url:
                                print(f"  -> Bắn lệnh RAG sang Embedding (CÓ ĐÍNH KÈM HÌNH ẢNH): {sq['query']} (Tủ: {sq['target_collection']}) | Tệp đích: {target_document_id}")
                            else:
                                print(f"  -> Bắn lệnh RAG sang Embedding: {sq['query']} (Tủ: {sq['target_collection']}) | Tệp đích: {target_document_id}")
                            db.collection("llm14b_to_embedding_tasks").document(f"{request_id}_sub{sub_index}").set(task_data)
                        
                    # 3. Phân phát lệnh cho Qwen (nếu có ảnh ngoài)
                    if send_to_qwen:
                        qwen_sub_index = len(sub_queries) + 1
                        print(f"  -> Bắn lệnh sang Đội Qwen để phân tích ảnh tải lên...")
                        db.collection("llm14b_to_qwen_tasks").document(f"{request_id}_qwen").set({
                            "request_id": request_id,
                            "image_url": image_url,
                            "sub_tracking": {"sub_index": qwen_sub_index, "total_subs": total_subs},
                            "status": "pending",
                            "timestamp": firestore.SERVER_TIMESTAMP
                        })
                            
                except Exception as e:
                    print(f"[LỖI LLM14b - KHỞI TẠO REQUEST]: {e}")
                    db.collection("ui_to_llm14b_tasks").document(doc_id).update({"status": "error"})

# HÀM GOM KẾT QUẢ CHUNG (TỪ DB HOẶC TỪ QWEN)
def xu_ly_manh_ghep_tra_ve(doc_id, doc_data, source_name):
    request_id = doc_data.get("request_id")
    sub_tracking = doc_data.get("sub_tracking", {})
    results = doc_data.get("search_results", []) if source_name == "DB" else [doc_data.get("qwen_result")]
    
    # Gắn thẻ nhãn xuất xứ vào từng chunk kết quả (Query Decomposition & Provenance Tracking)
    sub_query_text = sub_tracking.get("sub_query", "Không rõ")
    target_col = doc_data.get("target_collection", "Unknown")
    source_chunk_index = sub_tracking.get("source_chunk_index")
    for r in results:
        if isinstance(r, dict):
            r["_sub_query_tag"] = sub_query_text
            r["_target_collection_tag"] = target_col
            if source_chunk_index is not None:
                r["_source_chunk_index"] = source_chunk_index
            
    with memory_lock:
        if request_id not in active_requests:
            return False # Ignored
            
        req_state = active_requests[request_id]
        req_state["received_subs"] += 1
        
        if doc_data.get("is_counting_query"):
            count_val = doc_data.get("total_count", 0)
            req_state["total_count"] = req_state.get("total_count", 0) + count_val
            
            target_collection = doc_data.get("target_collection", "Unknown")
            collection_name_map = {
                "image_chunks": "Hình ảnh/Biểu đồ",
                "table_chunks": "Bảng biểu",
                "text_chunks": "Văn bản",
                "formula_chunks": "Công thức",
                "code_chunks": "Mã nguồn",
                "toc_chunks": "Mục lục"
            }
            collection_vn = collection_name_map.get(target_collection, target_collection)
            summary_sentence = f"[BÁO CÁO HỆ THỐNG ĐẾM SỐ LƯỢNG] TÌM THẤY CHÍNH XÁC {count_val} {collection_vn}."
            
            summary_item = {
                "du_lieu": {
                    "content": summary_sentence
                },
                "_sub_query_tag": sub_query_text,
                "_target_collection_tag": target_col
            }
            req_state["sub_results"].append(summary_item)
            req_state["sub_results"].extend(results)
        else:
            req_state["sub_results"].extend(results)
        
        print(f"[LLM14b] Gom được mảnh ghép từ {source_name} (Tiến độ: {req_state['received_subs']}/{req_state['total_subs']})")
        
        if req_state["received_subs"] == req_state["total_subs"]:
            print(f" ĐÃ ĐỦ MẢNH GHÉP (Chặng {req_state.get('stage', 1)}).")
            update_llm_progress(req_state["ui_doc_id"], f"Đã gom đủ dữ liệu (Chặng {req_state.get('stage', 1)}). Đang nghiệm thu...")
            
            # LUỒNG MULTI-HOP V2: TUYỂN CHỌN rồi LÀM GIÀU (Filter-then-Enrich)
            is_counting_query = req_state.get("is_counting_query", False)
            is_fetch_all = req_state.get("is_fetch_all_content", False)
            if req_state.get("stage", 1) == 1 and not is_counting_query:
                # Phân loại: Ảnh/Bảng (có prev/next) vs Văn bản thuần
                multimodal_chunks = [res for res in req_state["sub_results"] if "prev_text_snippet" in res.get("du_lieu", {}) and "next_text_snippet" in res.get("du_lieu", {})]
                text_chunks = [res for res in req_state["sub_results"] if res not in multimodal_chunks]
                
                if is_fetch_all:
                    selected_multimodal = multimodal_chunks
                    selected_text = text_chunks
                    print(f"  -> Bỏ qua tuyển chọn Chặng 1 do cờ fetch_all.")
                else:
                    selected_multimodal = []
                    if multimodal_chunks:
                        update_llm_progress(req_state["ui_doc_id"], f"Phát hiện {len(multimodal_chunks)} đối tượng Ảnh/Bảng. Đang duyệt...")
                        selected_multimodal = llm_tuyen_chon_chang_1(req_state["original_query"], multimodal_chunks, req_state.get("history", []))
                    
                    selected_text = []
                    if text_chunks:
                        update_llm_progress(req_state["ui_doc_id"], f"Phát hiện {len(text_chunks)} đoạn Văn bản. Đang để AI lọc nội dung rác...")
                        selected_text = llm_tuyen_chon_chang_1(req_state["original_query"], text_chunks, req_state.get("history", []))
                
                # Cập nhật stage_1_results CHỈ chứa các kết quả đã vượt qua bộ lọc
                req_state["stage_1_results"] = selected_text.copy()
                
                if selected_multimodal:
                    print(f"  -> Đã duyệt {len(selected_multimodal)} đối tượng Ảnh/Bảng. Chuẩn bị Làm giàu (Chặng 2)...")
                    for i, chunk in enumerate(selected_multimodal):
                        payload = chunk.get("du_lieu", {})
                        original_content = payload.get("content") or ""
                        core_info = get_core_info_for_chunk(payload, original_content)
                        if not core_info:
                            core_info = "Không có thông tin cốt lõi"
                        # Đánh số thứ tự đối tượng để khi lên giao diện nó rành mạch
                        payload["content"] = f"[Đối tượng số {i+1}]:\n{core_info}"
                        
                    req_state["stage_1_results"].extend(selected_multimodal)
                    req_state["selected_chunks"] = selected_multimodal  # Lưu danh sách đã duyệt
                    
                    # === CHẶNG 2: LÀM GIÀU (Tìm Text bổ sung cho Ảnh/Bảng đã duyệt) ===
                    expansion_queries = llm_tao_truy_van_mo_rong_v2(selected_multimodal, is_fetch_all)
                    
                    if len(expansion_queries) > 0:
                        req_state["stage"] = 2
                        req_state["received_subs"] = 0
                        req_state["total_subs"] = len(expansion_queries)
                        req_state["sub_results"] = []  # Xóa trắng để hứng data Chặng 2
                        update_llm_progress(req_state["ui_doc_id"], f"Bắn {len(expansion_queries)} lệnh tìm Text bổ sung cho {len(selected_multimodal)} đối tượng...")
                        for idx, sq in enumerate(expansion_queries):
                            sub_index = 100 + idx
                            print(f"  -> Bắn lệnh Làm Giàu [{idx+1}]: '{sq['query'][:80]}...' (Tủ: {sq['target_collection']})")
                            db.collection("llm14b_to_embedding_tasks").document(f"{request_id}_sub{sub_index}").set({
                                "request_id": request_id,
                                "query": sq["query"],
                                "query_image_url": None, 
                                "trong_pdf": True,
                                "target_collection": sq["target_collection"],
                                "target_document_id": "ALL",
                                "sub_tracking": {"sub_index": sub_index, "total_subs": len(expansion_queries), "source_chunk_index": sq.get("source_chunk_index")},
                                "status": "pending",
                                "timestamp": firestore.SERVER_TIMESTAMP
                            })
                        return  # Chờ dữ liệu Chặng 2 dội về
                
                # Nếu không lọt vào Chặng 2 (không có multimodal), gán thẳng kết quả đã lọc vào sub_results
                req_state["sub_results"] = req_state["stage_1_results"]
                print("  -> Đi thẳng tới Trạm tổng hợp.")

            # GỘP DỮ LIỆU CHẶNG 2 (Nếu đang ở Chặng 2)
            if req_state.get("stage", 1) == 2:
                update_llm_progress(req_state["ui_doc_id"], "Đang nhờ LLM thẩm định dữ liệu Text bổ sung Chặng 2...")
                
                # sub_results lúc này CHỈ CHỨA các kết quả Text mới từ Chặng 2
                stage_2_text_results = req_state["sub_results"]
                
                # 1. Lọc thô bằng Vector Score >= 0.30
                valid_texts = []
                for res in stage_2_text_results:
                    score = res.get("do_chinh_xac", 0)
                    if score >= 0.30:
                        source_idx = res.get("_source_chunk_index")
                        if source_idx is not None and "du_lieu" in res:
                            res["du_lieu"]["content"] = f"[Văn bản bổ sung cho Đối tượng số {source_idx + 1}]:\n" + res["du_lieu"].get("content", "")
                        valid_texts.append(res)
                
                # 2. Lọc tinh bằng LLM (Gọi hàm llm_loc_text_vong_2)
                llm_filtered_texts = []
                if valid_texts:
                    # Gom nhóm theo từng mỏ neo (source_idx) để kiểm tra chéo với Caption
                    texts_by_source = {}
                    for res in valid_texts:
                        idx = res.get("_source_chunk_index")
                        if idx not in texts_by_source:
                            texts_by_source[idx] = []
                        texts_by_source[idx].append(res)
                        
                    for idx, texts in texts_by_source.items():
                        if idx is not None and idx < len(req_state.get("selected_chunks", [])):
                            anchor = req_state["selected_chunks"][idx]
                            caption = anchor.get("du_lieu", {}).get("caption", "Đối tượng không có chú thích")
                            approved = llm_loc_text_vong_2(caption, texts)
                            llm_filtered_texts.extend(approved)
                        else:
                            llm_filtered_texts.extend(texts) # Fallback nếu mất index
                
                # Gộp lại: TOÀN BỘ KẾT QUẢ CHẶNG 1 + Text bổ sung ĐÃ QUA ẢI LLM
                req_state["sub_results"] = req_state.get("stage_1_results", []) + llm_filtered_texts
                print(f"  -> Đã gộp: {len(req_state.get('stage_1_results', []))} mảnh Chặng 1 + {len(llm_filtered_texts)} mảnh Text bổ sung (đã qua ải LLM).")
            
            # TỰ KIỂM TRA CHẤT LƯỢNG (Self-Reflect)
            is_counting_query = req_state.get("is_counting_query", False)
            is_fetch_all = req_state.get("is_fetch_all_content", False)
            if is_counting_query or is_fetch_all:
                eval_result = {"status": "DU_THONG_TIN"}
                update_llm_progress(req_state["ui_doc_id"], "Câu hỏi đếm số lượng hoặc lấy toàn bộ, bỏ qua tự kiểm tra, đang tổng hợp kết quả...")
            else:
                update_llm_progress(req_state["ui_doc_id"], "Thẩm định viên AI đang soi xem dữ liệu có trả lời đúng trọng tâm không...")
                eval_result = llm_tu_kiem_tra(req_state["original_query"], req_state["sub_results"], req_state.get("history", []))
            
            if eval_result["status"] == "THIEU_THONG_TIN" and req_state["loop_count"] < 1:
                print("  -> BẮT ĐẦU VÒNG LẶP RAG MỚI do thiếu thông tin...")
                update_llm_progress(req_state["ui_doc_id"], "Dữ liệu chưa đạt yêu cầu! AI tự động lùng sục lại vòng 2...")
                # 1. Gọi LLM để viết lại truy vấn (Đổi chiến thuật)
                def format_hist(h):
                    if not h: return "Không"
                    return "\n".join([f"User: {t.get('question')}\nAI: {t.get('answer')}" for t in h[-2:]])
                rewrite_prompt = f"Lịch sử trò chuyện:\n{format_hist(req_state.get('history', []))}\n\nCâu hỏi gốc: {req_state['original_query']}\nKết quả tìm kiếm trước đó thất bại vì sai từ khóa. Hãy viết lại 1 câu truy vấn tìm kiếm khác (đồng nghĩa, hoặc viết dưới dạng keyword) để tìm kiếm lại. Đảm bảo thay thế các đại từ (nó, chúng) bằng danh từ cụ thể từ Lịch sử. CHỈ in ra câu truy vấn, không giải thích."
                try:
                    new_query = call_llm_with_retry(rewrite_prompt)
                    new_query = new_query.strip()
                    print(f"  -> Truy vấn mới: {new_query}")
                except:
                    new_query = req_state['original_query']
                
                # 2. Reset state cho vòng lặp mới
                req_state["loop_count"] += 1
                req_state["received_subs"] = 0
                # [SỬA LỖI]: Bắt buộc phải giữ lại mỏ neo (Ảnh/Bảng) từ Chặng 1, không được xóa trắng!
                req_state["sub_results"] = req_state.get("stage_1_results", []).copy()
                req_state["total_subs"] = 1
                
                # 3. Gửi lại lệnh Embedding
                db.collection("llm14b_to_embedding_tasks").document(f"{request_id}_sub1_retry").set({
                    "request_id": request_id,
                    "query": new_query,
                    "query_image_url": None, 
                    "trong_pdf": True,
                    "target_collection": "text_chunks", # Fallback tìm trong text
                    "target_document_id": "ALL",
                    "sub_tracking": {"sub_index": 1, "total_subs": 1},
                    "status": "pending",
                    "timestamp": firestore.SERVER_TIMESTAMP
                })
                # Kết thúc hàm ở đây, chờ kết quả mới quay về
            else:
                # TỔNG HỢP VÀ LƯU VÀO RAM LỊCH SỬ
                update_llm_progress(req_state["ui_doc_id"], "Đang chắp bút viết câu trả lời cuối cùng...")
                final_answer = llm_tong_hop_dap_an(
                    req_state["original_query"], 
                    req_state["sub_results"], 
                    list(conversation_history),
                    is_counting_query=is_counting_query,
                    total_count=req_state.get("total_count", 0)
                )
                
                # Đẩy vào RAM (Tự động xóa cái cũ nhất nếu > 5)
                conversation_history.append({
                    "turn_index": turn_counter,
                    "question": req_state["original_query"],
                    "answer": final_answer
                })
                
                # Trả UI
                db.collection("llm14b_to_ui_results").document(req_state["ui_doc_id"]).set({
                    "request_id": request_id,
                    "final_answer": final_answer,
                    "status": "done",
                    "timestamp": firestore.SERVER_TIMESTAMP
                })
                update_llm_progress(req_state["ui_doc_id"], "Xong! Đã gửi đáp án.")
                print(f" ĐÃ GỬI ĐÁP ÁN CHO UI. Đã lưu vào Bộ nhớ RAM.")
                del active_requests[request_id]
                
    return True

# LISTENER 2: HÓNG MẢNH GHÉP TỪ DATABASE (RAG)
def on_db_result_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED'] and change.document.to_dict().get("status") == "pending":
            db.collection("db_to_llm14b_results").document(change.document.id).update({"status": "processing"})
            success = xu_ly_manh_ghep_tra_ve(change.document.id, change.document.to_dict(), "DB")
            db.collection("db_to_llm14b_results").document(change.document.id).update({"status": "done" if success else "ignored"})

# LISTENER 3: HÓNG KẾT QUẢ TỪ QWEN VLM/CODER (PHÂN TÍCH ẢNH)
def on_qwen_result_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED'] and change.document.to_dict().get("status") == "pending":
            db.collection("qwen_to_llm14b_results").document(change.document.id).update({"status": "processing"})
            success = xu_ly_manh_ghep_tra_ve(change.document.id, change.document.to_dict(), "QWEN")
            db.collection("qwen_to_llm14b_results").document(change.document.id).update({"status": "done" if success else "ignored"})

# CHẠY VÒNG LẶP VÔ HẠN TRÊN COLAB
def start_llm_worker():
    print(" Bắt đầu khởi động Não bộ LLM14b (Worker)...")
    db.collection("ui_to_llm14b_tasks").on_snapshot(on_ui_chat_snapshot)
    db.collection("db_to_llm14b_results").on_snapshot(on_db_result_snapshot)
    db.collection("qwen_to_llm14b_results").on_snapshot(on_qwen_result_snapshot)
    
    print(f" Não bộ {ACTIVE_TEXT_PROVIDER.upper()} đang trực chiến! Đã kết nối với Database. Đang chờ câu hỏi từ UI... (Bấm Ctrl+C để thoát).")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(" Dừng Không gian não bộ.")

if __name__ == "__main__":
    start_llm_worker()
