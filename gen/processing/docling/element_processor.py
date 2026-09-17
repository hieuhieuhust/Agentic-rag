"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""

def convert_monospace_text_to_code(element_coords, pdf_path, mono_threshold=0.8):
    _pdf = fitz.open(pdf_path)
    code_fonts = set()
    code_count = 0

    class _BBox:
        def __init__(self, l, t, r, b): self.l, self.t, self.r, self.b = l, t, r, b

    # ── Chỉ nhận font là monospace thật sự ───────────────────────────────────
    MONO_KEYWORDS = {
        "mono", "code", "courier", "consolas", "console",
        "typewriter", "fixed", "terminal", "hack", "menlo",
        "inconsolata", "iosevka", "fira", "jetbrains", "cascadia",
        "ubuntu mono", "source code", "roboto mono", "ibm plex mono",
        "lucida console", "anonymous", "droid sans mono",
    }

    def is_truly_monospace(font_name):
        f = font_name.lower()
        return any(kw in f for kw in MONO_KEYWORDS)

    # ── Học font code thật từ PDF (chỉ học nếu thật sự là mono) ─────────────
    for e in element_coords:
        if str(e.get("type")).lower() == "code":
            page = _pdf[e["page"] - 1]
            bbox = _BBox(e["bbox_l"], e["bbox_t"], e["bbox_r"], e["bbox_b"])
            info = dominant_span_info(page, bbox, page.rect.height)
            if info and is_truly_monospace(info["base_font"]):   # ← thêm điều kiện này
                code_fonts.add(info["base_font"].lower())
            code_count += 1
            if code_count >= 5: break

    default_monospace = {
        "ubuntumono", "ubuntu mono", "consolas",
        "courier", "courier new", "fira code", "jetbrains mono"
    }
    target_fonts = code_fonts | default_monospace

    # ── Tính tỉ lệ ký tự monospace trong 1 element ───────────────────────────
    def monospace_ratio(page, bbox, page_height):
        rect = fitz.Rect(bbox.l, page_height - bbox.t, bbox.r, page_height - bbox.b)
        total_chars = 0
        mono_chars  = 0
        for b in page.get_text("dict", clip=rect)["blocks"]:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    t = span["text"].strip()
                    if not t:
                        continue
                    char_count   = len(t)
                    total_chars += char_count
                    bfont = base_font(span["font"]).lower()
                    if any(f in bfont for f in target_fonts):
                        mono_chars += char_count
        if total_chars == 0:
            return 0.0
        return mono_chars / total_chars

    # ── Duyệt và chuyển đổi ──────────────────────────────────────────────────
    converted_count = 0
    for e in element_coords:
        original_type = str(e.get("type")).lower()
        if original_type not in ["text", "list_item", "table"]:
            continue
        page  = _pdf[e["page"] - 1]
        bbox  = _BBox(e["bbox_l"], e["bbox_t"], e["bbox_r"], e["bbox_b"])
        ratio = monospace_ratio(page, bbox, page.rect.height)
        if ratio >= mono_threshold:
            e["original_type"] = original_type
            e["type"]          = "code"
            converted_count   += 1

    _pdf.close()
    print(f" Đã chuyển đổi thành công {converted_count} đoạn thành code!")
    return element_coords

import fitz

import re

def split_picture_containing_code(element_coords, pdf_path):
    _pdf = fitz.open(pdf_path)
    def get_base_font(fname):
        return re.sub(r"[-,]?(bold|italic|regular|roman|light|medium|black|heavy|demi|semibold|oblique).*", "", fname, flags=re.IGNORECASE).strip().lower()

    code_fonts = set()
    code_count = 0
    class _BBox:
        def __init__(self, l, t, r, b): self.l, self.t, self.r, self.b = l, t, r, b

    for e in element_coords:
        if str(e.get("type")).lower() == "code":
            page = _pdf[e["page"] - 1]
            bbox = _BBox(e["bbox_l"], e["bbox_t"], e["bbox_r"], e["bbox_b"])
            info = dominant_span_info(page, bbox, page.rect.height)
            if info: code_fonts.add(info["base_font"].lower())
            code_count += 1
            if code_count >= 5: break

    default_monospace = {
        # Cổ điển & Mặc định hệ thống
        "courier", "courier new", "consolas", "monaco", "lucida console",
        "andale mono", "fixedsys", "terminal", "vga", "freemono", "nimbus mono",
        "courier prime", "consolemono", "prestige elite", "letter gothic",
        "system mono", "monospace", "lucida sans typewriter", "ms gothic",
        "ms mincho", "couriernewpsmt", "courier-bold", "courier-oblique",

        # Các font lập trình hiện đại & Nổi tiếng nhất
        "fira code", "firacode", "fira mono", "source code pro", "sourcecode",
        "jetbrains mono", "jetbrainsmono", "cascadia code", "cascadiacode", "cascadia mono",
        "ubuntu mono", "ubuntumono", "roboto mono", "robotomono", "hack", "menlo",
        "inconsolata", "sf mono", "sfmono", "ibm plex mono", "ibmplexmono",
        "sf mono compact", "menlo regular", "cascadia code pl", "cascadia code nf",

        # Họ font mã nguồn mở & Linux
        "dejavu sans mono", "dejavumono", "bitstream vera sans mono", "liberation mono",
        "droid sans mono", "noto sans mono", "oxygen mono", "pt mono", "space mono",
        "spacemono", "dejavusansmono",

        # Các font lập trình chuyên dụng (Custom/Hacker)
        "anonymous pro", "iosevka", "victor mono", "operator mono", "dank mono",
        "pragmatapro", "meslo", "terminus", "monoid", "go mono", "input mono",
        "envy code r", "fantasque sans mono", "monofur", "cutive mono", "share tech mono",
        "nova mono", "vt323", "syne mono", "xanh mono", "b612 mono", "cousine",
        "overpass mono", "spleen", "agave", "ocr a", "ocr-a", "proggy", "m+ mono",
        "comic mono",

        # Font hiện đại khác
        "recursive mono", "commit mono", "commitmono", "red hat mono",
        "geist mono", "berkeley mono", "maple mono", "sarasa mono",
        "0xproto", "martian mono",

        # Font Nerd Font
        "firacode nerd font", "jetbrainsmono nerd font", "hack nerd font",
        "meslo nerd font", "cascadia nerd font",

        # Font monospace tiếng Việt/CJK hay gặp
        "noto sans mono cjk", "sarasa term", "sarasa fixed",

        # Font cổ/hiếm
        "prestige", "line printer", "teletype", "px437", "perfect dos vga 437",

        # Biến thể viết liền không dấu cách
        "couriernew", "lucidaconsole", "sourcecodepro", "ibmplexmono",
        "robotomono", "firamono",

        # Font hay gặp trong file PDF
        "latin modern mono", "latinmodernmono", "computer modern typewriter",
        "computer modern mono", "cmtt", "cmtt10", "lmmono", "lmmono10",
        "nimbus mono ps", "courier10bt", "prestige elite std",
    }

    target_fonts = code_fonts | default_monospace

    new_element_coords = []
    split_count = 0

    for e in element_coords:
        if str(e.get("type")).lower() == "picture":
            page = _pdf[e["page"] - 1]
            page_height = page.rect.height
            pic_l, pic_r = e["bbox_l"], e["bbox_r"]

            y0 = page_height - e["bbox_t"]
            y1 = page_height - e["bbox_b"]
            rect = fitz.Rect(pic_l, y0, pic_r, y1)

            mono_spans = []
            blocks = page.get_text("dict", clip=rect).get("blocks", [])
            for b in blocks:
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text: continue
                        bfont = get_base_font(span["font"])
                        if any(f in bfont for f in target_fonts):
                            mono_spans.append(span["bbox"])

            if mono_spans:
                mono_y0 = min(s[1] for s in mono_spans)
                mono_y1 = max(s[3] for s in mono_spans)
                dist_to_top = abs(mono_y0 - y0)
                dist_to_bottom = abs(y1 - mono_y1)

                code_elem = e.copy()
                code_elem["type"] = "code"

                if dist_to_top <= dist_to_bottom:
                    code_y0, code_y1 = y0, mono_y1
                    pic_new_y0, pic_new_y1 = mono_y1 + 5, y1
                    code_goes_first = True
                else:
                    code_y0, code_y1 = mono_y0, y1
                    pic_new_y0, pic_new_y1 = y0, mono_y0 - 5
                    code_goes_first = False

                if pic_new_y1 > pic_new_y0:
                    code_elem["bbox_t"] = round(page_height - code_y0, 1)
                    code_elem["bbox_b"] = round(page_height - code_y1, 1)
                    code_rect = fitz.Rect(pic_l, code_y0, pic_r, code_y1)
                    code_elem["text"] = page.get_text("text", clip=code_rect).strip()
                    # THÊM NHÃN GỐC Ở ĐÂY
                    code_elem["original_type"] = "picture_split"

                    e["bbox_t"] = round(page_height - pic_new_y0, 1)
                    e["bbox_b"] = round(page_height - pic_new_y1, 1)

                    if code_goes_first: new_element_coords.extend([code_elem, e])
                    else: new_element_coords.extend([e, code_elem])
                    split_count += 1
                    continue
                else:
                    e["type"] = "code"
                    code_rect = fitz.Rect(pic_l, code_y0, pic_r, code_y1)
                    e["text"] = page.get_text("text", clip=code_rect).strip()
                    # THÊM NHÃN GỐC Ở ĐÂY
                    e["original_type"] = "picture_full"
                    new_element_coords.append(e)
                    continue

        new_element_coords.append(e)

    _pdf.close()
    return new_element_coords

def fix_tables_misidentified_as_pictures(element_coords, doc, caption_keywords=("hình", "figure")):
    """
    Duyệt các TABLE trong doc, nếu caption đi kèm BẮT ĐẦU BẰNG "hình"/"figure"
    thì coi đây thực chất là PICTURE bị nhận nhầm thành TABLE -> đổi type
    tương ứng trong element_coords (dùng bbox từ find_heading để định vị
    đúng entry cần sửa).

    Trả về: element_coords đã sửa (list mới), danh sách các entry đã đổi type.
    """
    from docling_core.types.doc import DocItemLabel

    def _get_caption_text_for_item(item):
        captions = getattr(item, "captions", None) or []
        texts = []
        for cap_ref in captions:
            try:
                cap_item = cap_ref.resolve(doc)
            except AttributeError:
                cap_item = cap_ref
            if cap_item is not None:
                texts.append(getattr(cap_item, "text", "") or "")
        return " ".join(texts)

    def _bbox_match(e, prov_bbox, tol=1.0):
        return (
            abs(e["bbox_l"] - prov_bbox.l) <= tol and
            abs(e["bbox_t"] - prov_bbox.t) <= tol and
            abs(e["bbox_r"] - prov_bbox.r) <= tol and
            abs(e["bbox_b"] - prov_bbox.b) <= tol
        )

    new_element_coords = [dict(e) for e in element_coords]
    fixed_entries = []

    for item, _level in doc.iterate_items():
        if item.label != DocItemLabel.TABLE or not item.prov:
            continue

        caption_text = _get_caption_text_for_item(item).strip().lower()
        is_actually_picture = any(caption_text.startswith(kw) for kw in caption_keywords)
        if not is_actually_picture:
            continue

        prov = item.prov[0]
        for e in new_element_coords:
            if e["page"] == prov.page_no and e["type"] == "table" and _bbox_match(e, prov.bbox):
                e["type"] = "picture"
                fixed_entries.append({
                    "page": e["page"],
                    "bbox": (e["bbox_l"], e["bbox_t"], e["bbox_r"], e["bbox_b"]),
                    "old_type": "table",
                    "new_type": "picture",
                    "caption": caption_text[:80],
                })

    print(f" Đã sửa {len(fixed_entries)} TABLE nhận nhầm -> PICTURE (theo caption 'hình'/'figure')")
    for f in fixed_entries:
        print(f"  trang {f['page']:<4} bbox={f['bbox']}  caption='{f['caption']}'")

    return new_element_coords, fixed_entries

def merge_pictures_by_coordinates(pdf_path, element_coords, struct_merged, doc, edge_tolerance=20.0):
    """
    Gom nhóm các PICTURE trên cùng 1 trang dựa theo toạ độ:
      - Cùng trang
      - Có ít nhất 1 mốc (trên/dưới/trái/phải) lệch nhau < edge_tolerance
      - Không có vật cản (table/text/heading/ảnh khác/caption) chen giữa
        theo đúng phương đang xét
    Gộp dây chuyền (union-find) để xử lý được nhóm 3-4 ảnh liên tiếp.
    Ảnh sau khi gộp lấy caption/text từ ảnh NÀO TRONG NHÓM CÓ CAPTION
    (tra qua doc.iterate_items() + item.captions); nếu cả nhóm không ảnh
    nào có caption thì lấy field từ ảnh đầu tiên như cũ.

    Trả về: element_coords mới (đã gộp), danh sách các nhóm đã gộp.
    """
    from docling_core.types.doc import DocItemLabel

    def _get_all_obstacles_on_page(page_no):
        obstacles = []
        for e in element_coords:
            if e["page"] != page_no or e["type"] == "picture":
                continue
            obstacles.append((e["bbox_l"], e["bbox_t"], e["bbox_r"], e["bbox_b"], e["type"]))
        for r in struct_merged:
            if r["page"] != page_no:
                continue
            obstacles.append((r["bbox_l"], r["bbox_t"], r["bbox_r"], r["bbox_b"], "heading"))
        for item, _level in doc.iterate_items():
            if item.label != DocItemLabel.CAPTION or not item.prov:
                continue
            prov = item.prov[0]
            if prov.page_no != page_no:
                continue
            bbox = prov.bbox
            obstacles.append((bbox.l, bbox.t, bbox.r, bbox.b, "caption"))
        return obstacles

    def _is_between_horizontal(obstacle, box_a, box_b):
        o_l, o_t, o_r, o_b, _kind = obstacle
        l_a, t_a, r_a, b_a = box_a
        l_b, t_b, r_b, b_b = box_b

        left_box, right_box = (box_a, box_b) if l_a < l_b else (box_b, box_a)
        gap_l = left_box[2]
        gap_r = right_box[0]
        if gap_l >= gap_r:
            return False

        if o_r < gap_l or o_l > gap_r:
            return False

        min_t = min(t_a, t_b)
        max_b = max(b_a, b_b)
        if o_b > min_t or o_t < max_b:
            return False

        return True

    def _is_between_vertical(obstacle, box_a, box_b):
        o_l, o_t, o_r, o_b, _kind = obstacle
        l_a, t_a, r_a, b_a = box_a
        l_b, t_b, r_b, b_b = box_b

        top_box, bottom_box = (box_a, box_b) if t_a > t_b else (box_b, box_a)
        gap_t = top_box[3]
        gap_b = bottom_box[1]
        if gap_b >= gap_t:
            return False

        if o_t < gap_b or o_b > gap_t:
            return False

        min_l = min(l_a, l_b)
        max_r = max(r_a, r_b)
        if o_r < min_l or o_l > max_r:
            return False

        return True

    def _find_shared_edge_direction(box_a, box_b, tol):
        l1, t1, r1, b1 = box_a
        l2, t2, r2, b2 = box_b

        same_top    = abs(t1 - t2) <= tol
        same_bottom = abs(b1 - b2) <= tol
        same_left   = abs(l1 - l2) <= tol
        same_right  = abs(r1 - r2) <= tol

        if same_top or same_bottom:
            return "horizontal"
        if same_left or same_right:
            return "vertical"
        return None

    def _can_merge_pair(box_a, box_b, page_no):
        direction = _find_shared_edge_direction(box_a, box_b, edge_tolerance)
        if direction is None:
            return False

        obstacles = _get_all_obstacles_on_page(page_no)
        check_fn = _is_between_horizontal if direction == "horizontal" else _is_between_vertical

        for obs in obstacles:
            if check_fn(obs, box_a, box_b):
                return False

        return True

    def _bbox_match(e, prov_bbox, tol=1.0):
        return (
            abs(e["bbox_l"] - prov_bbox.l) <= tol and
            abs(e["bbox_t"] - prov_bbox.t) <= tol and
            abs(e["bbox_r"] - prov_bbox.r) <= tol and
            abs(e["bbox_b"] - prov_bbox.b) <= tol
        )

    def _get_caption_text_for_entry(entry):
        """Tra trong doc xem entry (1 picture trong element_coords) có caption
        thật sự đi kèm không (qua item.captions). Trả về text caption hoặc None."""
        for item, _level in doc.iterate_items():
            if item.label != DocItemLabel.PICTURE or not item.prov:
                continue
            prov = item.prov[0]
            if prov.page_no != entry["page"] or not _bbox_match(entry, prov.bbox):
                continue
            captions = getattr(item, "captions", None) or []
            for cap_ref in captions:
                try:
                    cap_item = cap_ref.resolve(doc)
                except AttributeError:
                    cap_item = cap_ref
                if cap_item is not None and getattr(cap_item, "text", ""):
                    return cap_item.text
        return None

    pictures = [
        (idx, e) for idx, e in enumerate(element_coords) if e["type"] == "picture"
    ]

    parent = {idx: idx for idx, _ in pictures}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    by_page = {}
    for idx, e in pictures:
        by_page.setdefault(e["page"], []).append((idx, e))

    for page_no, items in by_page.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                idx_a, e_a = items[i]
                idx_b, e_b = items[j]
                box_a = (e_a["bbox_l"], e_a["bbox_t"], e_a["bbox_r"], e_a["bbox_b"])
                box_b = (e_b["bbox_l"], e_b["bbox_t"], e_b["bbox_r"], e_b["bbox_b"])
                if _can_merge_pair(box_a, box_b, page_no):
                    union(idx_a, idx_b)

    groups = {}
    for idx, _e in pictures:
        root = find(idx)
        groups.setdefault(root, []).append(idx)

    new_element_coords = [dict(e) for e in element_coords]
    merged_groups_info = []
    indices_to_remove = set()

    for root, idx_list in groups.items():
        if len(idx_list) < 2:
            continue

        boxes = [
            (
                new_element_coords[i]["bbox_l"],
                new_element_coords[i]["bbox_t"],
                new_element_coords[i]["bbox_r"],
                new_element_coords[i]["bbox_b"],
            )
            for i in idx_list
        ]
        ls = [b[0] for b in boxes]
        ts = [b[1] for b in boxes]
        rs = [b[2] for b in boxes]
        bs = [b[3] for b in boxes]
        merged_bbox = (min(ls), max(ts), max(rs), min(bs))

        # ── Tìm ảnh nào trong nhóm CÓ caption thật sự, lấy làm base_entry ──
        base_idx = idx_list[0]
        caption_text_found = None
        for i in idx_list:
            cap_text = _get_caption_text_for_entry(new_element_coords[i])
            if cap_text:
                base_idx = i
                caption_text_found = cap_text
                break

        base_entry = dict(new_element_coords[base_idx])
        base_entry.update({
            "bbox_l": round(merged_bbox[0], 1),
            "bbox_t": round(merged_bbox[1], 1),
            "bbox_r": round(merged_bbox[2], 1),
            "bbox_b": round(merged_bbox[3], 1),
        })
        if caption_text_found:
            base_entry["text"] = caption_text_found[:120]

        for i in idx_list:
            indices_to_remove.add(i)

        new_element_coords.append(base_entry)
        merged_groups_info.append({
            "page": base_entry["page"],
            "count_merged": len(idx_list),
            "merged_bbox": merged_bbox,
            "caption_used": caption_text_found[:80] if caption_text_found else None,
        })

    final_element_coords = [
        e for i, e in enumerate(new_element_coords) if i not in indices_to_remove
    ]

    print(f" Đã gộp {len(merged_groups_info)} nhóm hình theo toạ độ")
    for g in merged_groups_info:
        cap_info = f"caption='{g['caption_used']}'" if g['caption_used'] else "(không có caption)"
        print(f"  trang {g['page']:<4} gộp {g['count_merged']} hình -> bbox={g['merged_bbox']}  {cap_info}")

    return final_element_coords, merged_groups_info

def add_caption_field_to_element_coords(element_coords, doc):
    """
    Thêm field "caption" (mặc định None) vào MỌI entry trong element_coords.
    Chỉ những entry PICTURE/TABLE nào thực sự có caption (tra qua item.captions
    trong doc) mới được điền giá trị caption tương ứng; các entry khác giữ None.
    """
    from docling_core.types.doc import DocItemLabel

    def _bbox_match(e, prov_bbox, tol=1.0):
        return (
            abs(e["bbox_l"] - prov_bbox.l) <= tol and
            abs(e["bbox_t"] - prov_bbox.t) <= tol and
            abs(e["bbox_r"] - prov_bbox.r) <= tol and
            abs(e["bbox_b"] - prov_bbox.b) <= tol
        )

    new_element_coords = [dict(e) for e in element_coords]

    # Mặc định caption = None cho toàn bộ entry
    for e in new_element_coords:
        e["caption"] = None

    # Chỉ tra caption cho PICTURE / TABLE (khớp bbox với doc)
    for item, _level in doc.iterate_items():
        if item.label not in (DocItemLabel.PICTURE, DocItemLabel.TABLE) or not item.prov:
            continue

        captions = getattr(item, "captions", None) or []
        caption_texts = []
        for cap_ref in captions:
            try:
                cap_item = cap_ref.resolve(doc)
            except AttributeError:
                cap_item = cap_ref
            if cap_item is not None and getattr(cap_item, "text", ""):
                caption_texts.append(cap_item.text)

        if not caption_texts:
            continue

        prov = item.prov[0]
        for e in new_element_coords:
            if e["page"] == prov.page_no and e["type"] == item.label.value and _bbox_match(e, prov.bbox):
                e["caption"] = " ".join(caption_texts)

    n_with_caption = sum(1 for e in new_element_coords if e["caption"] is not None)
    print(f" Đã thêm field 'caption' cho {len(new_element_coords)} entry, trong đó {n_with_caption} entry có caption")

    return new_element_coords
