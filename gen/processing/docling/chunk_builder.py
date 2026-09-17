"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""

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
