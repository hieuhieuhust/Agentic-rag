"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""

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
