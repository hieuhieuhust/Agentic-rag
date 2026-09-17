"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""

import fitz

def filter_monospace_headings(struct_merged, element_coords, pdf_path):
    """Lọc bỏ các heading có font monospace (từ 5 đoạn CODE đầu tiên + 10 font mặc định)"""
    code_fonts = set()
    code_count = 0
    _pdf_font = fitz.open(pdf_path)

    class _BBox:
        def __init__(self, l, t, r, b): self.l, self.t, self.r, self.b = l, t, r, b

    for e in element_coords:
        if e["type"] == "code":
            page = _pdf_font[e["page"] - 1]
            bbox = _BBox(e["bbox_l"], e["bbox_t"], e["bbox_r"], e["bbox_b"])
            info = dominant_span_info(page, bbox, page.rect.height)
            if info:
                code_fonts.add(info["base_font"].lower())
            code_count += 1
            if code_count >= 5:
                break

    monospace_fonts = {
        "courier", "consolas", "monaco", "inconsolata", "lucida console",
        "fira code", "source code pro", "menlo", "roboto mono", "jetbrains mono"
    }
    forbidden_fonts = code_fonts | monospace_fonts

    filtered_merged = []
    removed_headings = []   # ← MỚI: lưu lại các heading bị loại
    removed_count = 0

    for r in struct_merged:
        page = _pdf_font[r["page"] - 1]
        bbox = _BBox(r["bbox_l"], r["bbox_t"], r["bbox_r"], r["bbox_b"])
        info = dominant_span_info(page, bbox, page.rect.height)
        if info:
            bfont = info["base_font"].lower()
            is_forbidden = any(f in bfont for f in forbidden_fonts)
            if not is_forbidden:
                filtered_merged.append(r)
            else:
                removed_headings.append(r)   # ← lưu lại thay vì chỉ in ra
                removed_count += 1
        else:
            filtered_merged.append(r)

    print(f"Tổng kết: {len(filtered_merged)} giữ lại, {removed_count} bị loại")

    _pdf_font.close()
    return filtered_merged, removed_headings   # ← trả về thêm removed_headings

import fitz

from docling_core.types.doc import DocItemLabel

def resolve_removed_headings(struct_merged_filtered, removed_headings, element_coords):
    """
    Xử lý các heading đã bị loại bỏ (ví dụ do trùng font monospace):
      - Tìm element đứng NGAY SAU heading đó trong element_coords (cùng trang,
        gần nhất theo vị trí đọc: từ trên xuống, trái sang phải).
      - Nếu element đó là TEXT hoặc CODE -> gộp (union) bbox của heading vào bbox
        của element đó (mở rộng bbox của element để bao trọn cả heading).
      - Nếu element đó không phải TEXT/CODE (hoặc không tìm thấy) -> heading đó
        tự trở thành 1 item loại TEXT độc lập, thêm vào element_coords.

    Trả về:
      - element_coords đã được cập nhật (list mới, không sửa in-place)
      - removed_headings_log: log chi tiết xử lý từng heading bị loại
    """

    def reading_order_key(e):
        # Thứ tự đọc: trang tăng dần, rồi từ trên (t lớn) xuống dưới (t nhỏ), trái->phải
        return (e["page"], -e["bbox_t"], e["bbox_l"])

    # Sắp xếp element_coords theo thứ tự đọc để tìm "ngay sau" chính xác
    sorted_elements = sorted(element_coords, key=reading_order_key)

    new_element_coords = list(element_coords)  # copy, không sửa list gốc
    removed_headings_log = []

    for h in removed_headings:
        h_page = h["page"]
        h_bbox_t = h["bbox_t"]

        # Tìm element đứng ngay sau heading: cùng trang, có bbox_t nhỏ hơn
        # (tức nằm thấp hơn trên trang) và gần heading nhất
        candidates = [
            e for e in sorted_elements
            if e["page"] == h_page and e["bbox_t"] < h_bbox_t
        ]

        next_elem = None
        if candidates:
            # Gần nhất = bbox_t lớn nhất trong số các candidate (thấp hơn heading nhưng cao nhất trong nhóm đó)
            next_elem = max(candidates, key=lambda e: e["bbox_t"])

        if next_elem is not None and next_elem["type"] in (
            DocItemLabel.TEXT.value, DocItemLabel.CODE.value,
        ):
            # ── Gộp (union) bbox của heading vào bbox của next_elem ──
            old_bbox = (
                next_elem["bbox_l"], next_elem["bbox_t"],
                next_elem["bbox_r"], next_elem["bbox_b"],
            )

            next_elem["bbox_l"] = min(next_elem["bbox_l"], h["bbox_l"])
            next_elem["bbox_r"] = max(next_elem["bbox_r"], h["bbox_r"])
            next_elem["bbox_t"] = max(next_elem["bbox_t"], h["bbox_t"])
            next_elem["bbox_b"] = min(next_elem["bbox_b"], h["bbox_b"])

            removed_headings_log.append({
                "heading_text": h["text"], "page": h_page,
                "action": "merged_into_next", "merged_into_type": next_elem["type"],
                "old_bbox": old_bbox,
                "new_bbox": (next_elem["bbox_l"], next_elem["bbox_t"],
                             next_elem["bbox_r"], next_elem["bbox_b"]),
            })
        else:
            # ── Không đứng trước TEXT/CODE -> tự thành 1 item TEXT độc lập ──
            new_text_item = {
                "type": DocItemLabel.TEXT.value,
                "page": h_page,
                "bbox_l": h["bbox_l"], "bbox_t": h["bbox_t"],
                "bbox_r": h["bbox_r"], "bbox_b": h["bbox_b"],
                "text": h["text"],
            }
            new_element_coords.append(new_text_item)

            removed_headings_log.append({
                "heading_text": h["text"], "page": h_page,
                "action": "converted_to_text",
                "next_elem_type": next_elem["type"] if next_elem else None,
            })

    return new_element_coords, removed_headings_log

import difflib

import re

def similar(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

def assign_levels_to_struct_merged(struct_merged, real_heading_muc_luc_level):
    # CHUẨN BỊ DỮ LIỆU
    toc_indices = {}
    available_tocs = []

    for item in real_heading_muc_luc_level:
        level = item.get("level", 1)
        idx_str = item.get("extracted_index", "").strip()
        raw_text = item.get("text", "").strip()

        # Gắn lại chỉ số vào text giống như dạng của struct_merged
        if idx_str:
            full_text = f"{idx_str} {raw_text}".strip().lower()
        else:
            full_text = raw_text.lower()

        available_tocs.append({
            "full_text": full_text,
            "level": level
        })

        # Lưu lại index để phục vụ Bước 2 (so dấu chấm)
        if idx_str and re.fullmatch(r'\d+(?:\.\d+)*', idx_str):
            toc_indices[idx_str] = level

    # DUYỆT TỪNG HEADING TRONG FILE PDF
    for r in struct_merged:
        txt_merged = r.get("text", "").strip().lower()

        # BƯỚC 1: Tìm nhóm khớp với mục lục (độ giống >= 70%)
        best_ratio = 0
        best_match_idx = -1

        # Rà từ trái sang phải trong danh sách TOC còn lại
        for i, toc_item in enumerate(available_tocs):
            ratio = similar(txt_merged, toc_item["full_text"])
            if ratio > best_ratio:
                best_ratio = ratio
                best_match_idx = i

        if best_ratio >= 0.70:
            r["level"] = available_tocs[best_match_idx]["level"]
            # CHỐT: Đã khớp thì "rút" luôn mục lục này ra để không bị so trùng nữa
            available_tocs.pop(best_match_idx)
            continue

        # BƯỚC 2: Tìm tiểu mục con và tính level dựa trên dấu chấm
        m = re.match(r'^\s*(\d+(?:\.\d+)*)\.?\s+', r.get("text", ""))
        if m:
            struct_idx = m.group(1)
            best_prefix = None

            # Tìm heading cha trong Mục lục
            for toc_idx in toc_indices:
                if struct_idx == toc_idx:
                    best_prefix = toc_idx
                    break
                elif struct_idx.startswith(toc_idx + "."):
                    if best_prefix is None or len(toc_idx) > len(best_prefix):
                        best_prefix = toc_idx

            if best_prefix:
                dots_struct = struct_idx.count(".")
                dots_prefix = best_prefix.count(".")
                level_diff = dots_struct - dots_prefix

                if level_diff > 0:
                    r["level"] = toc_indices[best_prefix] + level_diff
                    continue

        # BƯỚC 3: Không hợp lệ -> Gán None
        r["level"] = None

    return struct_merged

def get_missing_level_blocks(struct_merged):
    """
    Tìm và gom nhóm các heading bị sót (level=None) nằm kẹp giữa 2 heading hợp lệ.
    Chỉ xét các heading đằng sau Mục lục.
    """
    # 1. Tìm vị trí kết thúc của Mục lục
    toc_idx = -1
    keywords = {"mục lục", "table of contents", "contents", "mục lục sơ bộ"}
    for i, r in enumerate(struct_merged):
        if r.get("text", "").strip().lower() in keywords:
            toc_idx = i
            break

    start_idx = toc_idx + 1 if toc_idx != -1 else 0

    # 2. Quét để gom nhóm
    heading_con_sot_giua_2level = []
    prev_valid = None
    current_none_block = []

    for i in range(start_idx, len(struct_merged)):
        current_heading = struct_merged[i]

        if current_heading.get("level") is not None:
            if len(current_none_block) > 0:
                heading_con_sot_giua_2level.append({
                    "prev_valid": prev_valid,
                    "missing_headings": current_none_block,
                    "next_valid": current_heading
                })
                current_none_block = []
            prev_valid = current_heading
        else:
            current_none_block.append(current_heading)

    # Xử lý đoạn cuối file
    if len(current_none_block) > 0:
        heading_con_sot_giua_2level.append({
            "prev_valid": prev_valid,
            "missing_headings": current_none_block,
            "next_valid": None
        })

    return heading_con_sot_giua_2level

import fitz

def enrich_font_name(struct_merged, pdf_path):
    """
    Quét lại file PDF dựa trên tọa độ (bbox) đã có trong struct_merged
    để trích xuất chính xác font_name và bổ sung vào dữ liệu.
    """
    pdf = fitz.open(pdf_path)

    for r in struct_merged:
        page = pdf[r["page"] - 1]
        page_height = page.rect.height

        # Tọa độ bbox trong struct_merged là gốc dưới-trái (chuẩn Docling)
        # Cần đổi sang chuẩn trên-trái của PyMuPDF để quét
        rect = fitz.Rect(
            r["bbox_l"],
            page_height - r["bbox_t"],
            r["bbox_r"],
            page_height - r["bbox_b"]
        )

        best_font = "Unknown"
        best_len = -1

        # Tìm cụm từ dài nhất trong vùng bbox này để lấy font chuẩn nhất
        for b in page.get_text("dict", clip=rect).get("blocks", []):
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    t = span["text"].strip()
                    if len(t) > best_len:
                        best_len = len(t)
                        best_font = span["font"]

        # Lưu vào dict
        r["font_name"] = best_font

    pdf.close()
    return struct_merged

def assign_levels_for_missing_blocks(heading_con_sot_giua_2level):
    """
    Xác định và khôi phục level cho các khối heading bị None
    dựa trên font_name, font_size và khoảng cách tới heading trước.
    """
    for block in heading_con_sot_giua_2level:
        # 1. Tìm bậc nhỏ nhất 'a' (thứ hạng cao nhất, tức là giá trị số bé nhất)
        # giữa heading trước và sau khối này.
        levels = []
        if block["prev_valid"] and block["prev_valid"]["level"] is not None:
            levels.append(block["prev_valid"]["level"])
        if block["next_valid"] and block["next_valid"]["level"] is not None:
            levels.append(block["next_valid"]["level"])

        if levels:
            a = min(levels)
        else:
            a = 1  # Nếu khối lơ lửng không có cả trước lẫn sau

        # 2. Quét từ trên xuống dưới, phân nhóm theo font và gán bậc
        group_level_map = {}

        # Bậc của nhóm đầu tiên sẽ là a + 1 (Thấp hơn a 1 bậc)
        current_assign_level = a + 1

        for miss in block["missing_headings"]:
            f_name = miss.get("font_name", "Unknown")
            f_size = miss.get("font_size", 0)
            signature = (f_name, f_size)

            # Nếu gặp một định dạng font hoàn toàn mới trong khối này
            if signature not in group_level_map:
                group_level_map[signature] = current_assign_level
                current_assign_level += 1 # Nhóm tiếp theo sẽ bị tụt thêm 1 bậc

            # Gán level cho heading bị sót
            miss["level"] = group_level_map[signature]

def filter_suspects_from_elements(suspect_rows, element_coords, tolerance=2.0):
    """
    So sánh tọa độ, in ra các phần tử bị nhầm thành suspect heading,
    đồng thời loại bỏ chúng ra khỏi danh sách và trả về element_coords thật sự.
    """
    real_element_coords = []
    removed_count = 0

    print(f"\nBắt đầu lọc suspect heading khỏi element_coords (sai số {tolerance}px)...")
    print(f"{'Page':<6} | {'Tọa độ (L, T, R, B)':<30} | {'Loại Element':<15} | {'Nội dung Text (Bị loại bỏ)'}")
    print("-" * 110)

    # Duyệt từng element, nếu trùng với bất kỳ suspect nào thì bỏ qua, nếu không thì giữ lại
    for elem in element_coords:
        e_page = elem.get('page')
        e_l = elem.get('bbox_l', 0)
        e_t = elem.get('bbox_t', 0)
        e_r = elem.get('bbox_r', 0)
        e_b = elem.get('bbox_b', 0)

        is_suspect = False

        for suspect in suspect_rows:
            s_page = suspect.get('page')
            if s_page != e_page:
                continue

            s_l, s_t, s_r, s_b = suspect.get('bbox', (0, 0, 0, 0))

            # Kiểm tra xem tọa độ có trùng không
            if (abs(s_l - e_l) <= tolerance and
                abs(s_t - e_t) <= tolerance and
                abs(s_r - e_r) <= tolerance and
                abs(s_b - e_b) <= tolerance):
                is_suspect = True
                break

        if is_suspect:
            # Nếu trùng -> in ra và không thêm vào real_element_coords
            removed_count += 1
            bbox_str = f"({e_l}, {e_t}, {e_r}, {e_b})"
            e_type = str(elem.get('type', ''))

            text_preview = str(elem.get('text', '')).replace('\n', ' ')
            if len(text_preview) > 45:
                text_preview = text_preview[:42] + "..."

            print(f"{e_page:<6} | {bbox_str:<30} | {e_type:<15} | {text_preview}")
        else:
            # Không trùng -> đây là element thật sự
            real_element_coords.append(elem)

    print("-" * 110)
    print(f"Đã loại bỏ {removed_count} suspect headings ra khỏi element_coords.\n")

    return real_element_coords
