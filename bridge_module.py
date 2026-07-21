import fitz
import os

# MODULE MỚI: Lọc bỏ phần Mục Lục (Chỉ lấy nội dung thật)
def filter_elements_after_toc(element_coords, struct_merged):
    # 1. Tìm heading Mục lục
    toc_heading_idx = -1
    for i, h in enumerate(struct_merged):
        text_lower = h.get("text", "").strip().lower()
        if "mục lục" in text_lower or "table of contents" in text_lower:
            toc_heading_idx = i
            break
            
    if toc_heading_idx == -1:
        print(" Không tìm thấy Heading 'Mục lục'. Giữ nguyên toàn bộ dữ liệu.")
        return element_coords
        
    toc_level = struct_merged[toc_heading_idx].get("level")
    if toc_level is None:
        toc_level = 99
        
    # 2. Tìm Heading nội dung đầu tiên ngay SAU Mục lục
    # (Là heading có level nhỏ hơn hoặc bằng level của Mục lục)
    start_content_idx = -1
    for i in range(toc_heading_idx + 1, len(struct_merged)):
        lvl = struct_merged[i].get("level")
        if lvl is None:
            lvl = 99
        if lvl <= toc_level:
            start_content_idx = i
            break
            
    if start_content_idx == -1:
        print(" Không tìm thấy nội dung sau Mục lục. Trả về toàn bộ dữ liệu.")
        return element_coords
        
    start_heading = struct_merged[start_content_idx]
    start_page = start_heading["page"]
    start_y = start_heading["bbox_t"]
    
    # 3. Lọc bỏ các element đứng TRƯỚC start_heading
    filtered_coords = []
    for elem in element_coords:
        # Nằm sau nếu: Trang lớn hơn HOẶC (Cùng trang và Tọa độ Y nhỏ hơn/bằng)
        # (Y càng nhỏ tức là càng nằm dưới cùng của trang)
        if elem["page"] > start_page or (elem["page"] == start_page and elem["bbox_t"] <= start_y):
            filtered_coords.append(elem)
            
    bi_loai_bo = len(element_coords) - len(filtered_coords)
    print(f" Đã cắt bỏ phần Mục Lục. Xóa đi {bi_loai_bo} elements rác. Giữ lại {len(filtered_coords)} elements nội dung.")
    
    return filtered_coords

# MODULE 1: Gắn Gia Phả (Heading Path) cho từng Element
def assign_heading_paths(element_coords, struct_merged):
    # Bước 1: Tiền xử lý struct_merged để tạo đường dẫn (path) cho mỗi heading
    path_stack = []
    
    for i, heading in enumerate(struct_merged):
        level = heading.get("level")
        if level is None:
            level = 99 # Xử lý fallback nếu sót level
            
        # Xóa các heading trong stack có level >= level hiện tại
        path_stack = [h for h in path_stack if h["level"] < level]
        
        # Heading cha chính là phần tử cuối cùng còn lại trong stack
        parent_text = path_stack[-1]["text"] if path_stack else "Root"
        
        # Đưa heading hiện tại vào stack
        path_stack.append({"level": level, "text": heading["text"]})
        
        # Tạo chuỗi heading_path
        heading_path = " > ".join([h["text"] for h in path_stack])
        
        # Tìm children (các heading phía dưới có level = level + 1)
        children = []
        for j in range(i + 1, len(struct_merged)):
            next_level = struct_merged[j].get("level")
            if next_level is None:
                next_level = 99
            if next_level <= level:
                break # Gặp heading đồng cấp hoặc to hơn thì dừng
            if next_level == level + 1:
                children.append(struct_merged[j]["text"])
                
        # Lưu lại thông tin vào struct_merged
        heading["heading_path"] = heading_path
        heading["heading_parent"] = parent_text
        heading["heading_children"] = children

    # Bước 2: Gắn heading path vào từng element trong element_coords
    for elem in element_coords:
        nearest_heading = None
        
        # Dò ngược struct_merged để tìm heading nằm ngay trên element này
        for heading in struct_merged:
            # Điều kiện nằm trên: Trang nhỏ hơn HOẶC (Cùng trang và tọa độ Y lớn hơn/bằng)
            # Lưu ý: Docling lấy gốc tọa độ Y ở dưới cùng trang, nên Y càng lớn tức là càng nằm bên trên
            if heading["page"] < elem["page"] or (heading["page"] == elem["page"] and heading["bbox_t"] >= elem["bbox_t"]):
                if nearest_heading is None or heading["page"] > nearest_heading["page"] or (heading["page"] == nearest_heading["page"] and heading["bbox_t"] <= nearest_heading["bbox_t"]):
                    nearest_heading = heading

        if nearest_heading:
            elem["heading_path"] = nearest_heading["text"] # Lấy đúng TÊN của Heading hiện tại
            elem["heading_parent"] = nearest_heading["heading_parent"]
            elem["heading_children"] = nearest_heading["heading_children"]
        else:
            elem["heading_path"] = "Root"
            elem["heading_parent"] = "Root"
            elem["heading_children"] = []

    print(" Đã gắn xong Gia Phả (Heading Path) cho các elements.")
    return element_coords

# MODULE 2: Gắn Ngữ Cảnh Xung Quanh (Context Snippets Sát Rạt)
def assign_context_snippets(element_coords, max_chars=300):
    for i, elem in enumerate(element_coords):
        if elem["type"] == "text":
            continue
            
        prev_text = ""
        next_text = ""
        
        # Liền trước: Phải là text VÀ không bị chắn bởi Heading (cùng chung heading_path)
        if i > 0:
            prev_elem = element_coords[i-1]
            if prev_elem["type"] == "text" and prev_elem.get("heading_path") == elem.get("heading_path"):
                prev_text = prev_elem.get("text", "")
                
        # Liền sau: Phải là text VÀ không bị chắn bởi Heading
        if i < len(element_coords) - 1:
            next_elem = element_coords[i+1]
            if next_elem["type"] == "text" and next_elem.get("heading_path") == elem.get("heading_path"):
                next_text = next_elem.get("text", "")
                
        elem["prev_text_snippet"] = prev_text[:max_chars]
        elem["next_text_snippet"] = next_text[:max_chars]

    print(" Đã gắn xong Context Snippets (Chỉ lấy text sát rạt, không bị chắn).")
    return element_coords

# MODULE 2.5: Trích xuất nội dung Bảng theo chiều ngang
def extract_full_table_text(element_coords, doc):
    from docling_core.types.doc import DocItemLabel
    
    for item, _level in doc.iterate_items():
        if item.label == DocItemLabel.TABLE and item.prov:
            prov = item.prov[0]
            # Dò tìm element table tương ứng trong element_coords
            for elem in element_coords:
                if elem["type"] == "table" and elem["page"] == prov.page_no:
                    # Sai số tọa độ nhỏ hơn 2.0
                    if abs(elem["bbox_t"] - prov.bbox.t) < 2.0:
                        try:
                            df = item.export_to_dataframe(doc)
                            # Ghép các ô thành hàng ngang, cách nhau bởi dấu "|"
                            horizontal_lines = []
                            for row_idx, row in enumerate(df.values):
                                line = " | ".join([str(val).replace('\n', ' ') if val is not None else "" for val in row])
                                horizontal_lines.append(f"Hàng {row_idx + 1}: {line}")
                            
                            elem["table_horizontal_text"] = "\n".join(horizontal_lines)
                        except Exception as e:
                            elem["table_horizontal_text"] = f"Lỗi đọc bảng: {str(e)}"
                            
    print(" Đã quét và đọc nội dung Table theo chiều ngang liền mạch.")
    return element_coords

# MODULE 3: Cắt Hình Ảnh Từ PDF
def crop_and_upload_images(element_coords, local_pdf_path, output_dir="cropped_images", supabase_client=None, doc_ai_id="unknown_doc"):
    """
    Cắt ảnh từ PDF, lưu tạm ra ổ cứng, sau đó upload lên Supabase Storage và lấy link public.
    """
    os.makedirs(output_dir, exist_ok=True)
    pdf = fitz.open(local_pdf_path)
    
    count = 0
    for i, elem in enumerate(element_coords):
        if elem["type"] == "picture":
            page = pdf[elem["page"] - 1]
            page_height = page.rect.height
            
            # Chuyển đổi hệ tọa độ: Docling (gốc dưới-trái) sang PyMuPDF (gốc trên-trái)
            y0 = page_height - elem["bbox_t"]
            y1 = page_height - elem["bbox_b"]
            
            if y0 > y1: # Đảm bảo y0 luôn nhỏ hơn y1
                y0, y1 = y1, y0
                
            rect = fitz.Rect(elem["bbox_l"], y0, elem["bbox_r"], y1)
            pix = page.get_pixmap(clip=rect)
            
            img_filename = f"image_page{elem['page']}_{i}.jpg"
            img_path = os.path.join(output_dir, img_filename)
            pix.save(img_path)
            
            elem["local_image_path"] = img_path
            
            # Upload lên Supabase nếu có client
            if supabase_client:
                remote_path = f"images/{doc_ai_id}/{img_filename}"
                try:
                    supabase_client.storage.from_("rag-data").upload(
                        path=remote_path,
                        file=img_path,
                        file_options={"content-type": "image/jpeg", "upsert": "true"}
                    )
                    public_url = supabase_client.storage.from_("rag-data").get_public_url(remote_path)
                    elem["image_ref"] = public_url
                except Exception as e:
                    print(f"     [Lỗi] Upload ảnh {img_filename} lên Supabase thất bại: {e}")
                    elem["image_ref"] = f"https://firebasestorage.googleapis.com/v0/b/your-app.appspot.com/o/{img_filename}?alt=media"
            else:
                elem["image_ref"] = f"https://firebasestorage.googleapis.com/v0/b/your-app.appspot.com/o/{img_filename}?alt=media"
                
            count += 1
            
    pdf.close()
    print(f" Đã cắt và lưu {count} hình ảnh vào thư mục '{output_dir}'.")
    return element_coords

# MODULE 4: Đóng Gói 5 Tủ JSON (Sẵn sàng gọi Embedding)
def package_chunks(element_coords, struct_merged=None, document_id="doc_001"):
    text_chunks = []
    image_chunks = []
    table_chunks = []
    formula_chunks = []
    code_chunks = []
    intro_chunks = [] # Tủ mới: Intro and Heading
    
    # 1. Quét qua struct_merged để tạo intro_chunks
    if struct_merged:
        for i, heading in enumerate(struct_merged):
            children = heading.get("heading_children", [])
            if children: # Chỉ tạo chunk nếu có heading con
                heading_text = heading.get("text", "Root")
                # Format câu văn theo ý tưởng của user
                children_str = '", "'.join(children)
                content = f'Mục "{heading_text}" chứa các nội dung "{children_str}"'
                
                chunk_id = f"{document_id}_intro_{i}"
                chunk = {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "page_number": heading.get("page", 1),
                    "heading_path": heading_text,
                    "content": content
                }
                intro_chunks.append(chunk)
    
    for i, elem in enumerate(element_coords):
        chunk_id = f"{document_id}_page{elem['page']}_chunk{i}"
        
        base_info = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "page_number": elem["page"],
            "heading_path": elem.get("heading_path", ""),
            "heading_parent": elem.get("heading_parent", ""),
            "heading_children": elem.get("heading_children", []),
        }
        
        if elem["type"] == "text":
            text_content = elem["text"]
            text_length = len(text_content)
            
            # Tính toán số lượng chunk dựa trên độ dài
            if text_length <= 800:
                num_chunks = 1
            elif 801 <= text_length <= 1000:
                num_chunks = 2
            elif 1001 <= text_length <= 1200:
                num_chunks = 3
            else:
                num_chunks = 4
                
            overlap = 200
            
            if num_chunks == 1:
                chunk = {**base_info, "content": text_content}
                text_chunks.append(chunk)
            else:
                # Thuật toán chia chunk với overlap cố định
                chunk_size = (text_length + overlap * (num_chunks - 1)) // num_chunks
                stride = chunk_size - overlap
                
                start = 0
                for c_idx in range(num_chunks):
                    end = min(start + chunk_size, text_length)
                    
                    if c_idx == num_chunks - 1:
                        chunk_text = text_content[start:]
                    else:
                        chunk_text = text_content[start:end]
                        
                    # Tạo chunk_id phân biệt cho các chunk nhỏ
                    sub_chunk_id = f"{chunk_id}_sub{c_idx+1}"
                    chunk = {**base_info, "chunk_id": sub_chunk_id, "content": chunk_text}
                    text_chunks.append(chunk)
                    
                    start += stride
            
        elif elem["type"] == "picture":
            chunk = {
                **base_info,
                "image_ref": elem.get("image_ref", ""),
                "local_image_path": elem.get("local_image_path", ""),
                "caption": elem.get("caption", ""),
                "prev_text_snippet": elem.get("prev_text_snippet", ""),
                "next_text_snippet": elem.get("next_text_snippet", ""),
            }
            image_chunks.append(chunk)
            
        elif elem["type"] == "table":
            chunk = {
                **base_info,
                "caption": elem.get("caption", ""),
                "table_horizontal_text": elem.get("table_horizontal_text", ""), # Trường mới đọc theo chiều ngang
                "raw_structure": elem.get("text", ""), 
                "prev_text_snippet": elem.get("prev_text_snippet", ""),
                "next_text_snippet": elem.get("next_text_snippet", ""),
            }
            table_chunks.append(chunk)
            
        elif elem["type"] == "formula":
            chunk = {
                **base_info,
                "latex": elem.get("text", ""), # Tạm dùng text, nếu có LaTeX thì thay đổi
                "prev_text_snippet": elem.get("prev_text_snippet", ""),
                "next_text_snippet": elem.get("next_text_snippet", ""),
            }
            formula_chunks.append(chunk)
            
        elif elem["type"] == "code":
            code_raw = elem.get("text", "")
            chunk = {
                **base_info,
                "code_raw": code_raw,
                "code_flattened": code_raw.replace("\n", " ").strip(),
                "shingles": code_raw.split("\n")[:5], # Cắt tạm 5 dòng đầu làm shingles
                "prev_text_snippet": elem.get("prev_text_snippet", ""),
                "next_text_snippet": elem.get("next_text_snippet", ""),
            }
            code_chunks.append(chunk)
            
    print(f" Đã đóng gói: {len(text_chunks)} Text, {len(image_chunks)} Image, {len(table_chunks)} Table, {len(formula_chunks)} Formula, {len(code_chunks)} Code, {len(intro_chunks)} Intro/Heading.")
    return {
        "text_chunks": text_chunks,
        "image_chunks": image_chunks,
        "table_chunks": table_chunks,
        "formula_chunks": formula_chunks,
        "code_chunks": code_chunks,
        "intro_chunks": intro_chunks
    }
