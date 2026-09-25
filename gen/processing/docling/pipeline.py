"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""

from processing.docling.element_processor import (
    add_caption_field_to_element_coords,
    convert_monospace_text_to_code,
    fix_tables_misidentified_as_pictures,
    merge_pictures_by_coordinates,
    split_picture_containing_code,
)
from processing.docling.heading_extractor import (
    build_struct_raw,
    dominant_span_info,
    get_bold_headings,
    is_bold,
)
from processing.docling.hierarchy_builder import (
    assign_levels_for_missing_blocks,
    assign_levels_to_struct_merged,
    enrich_font_name,
    filter_monospace_headings,
    filter_suspects_from_elements,
    get_missing_level_blocks,
    resolve_removed_headings,
)
from processing.docling.toc_analyzer import (
    assign_levels_and_build_tree,
    extract_bookmark_tree,
    extract_toc_headings,
    process_toc_v2,
)
from processing.docling.chunk_builder import package_chunks
from processing.docling.context_enricher import (
    assign_context_snippets,
    assign_heading_paths,
    filter_elements_after_toc,
)
from processing.docling.image_processor import crop_and_upload_images
from processing.docling.table_processor import extract_full_table_text

import fitz

from docling_core.types.doc import DocItemLabel

def find_heading(pdf_path, doc):

    heading_raw_elements, heading_signatures = get_bold_headings(doc, pdf_path)

    # ── BƯỚC 1.4: Lấy heading từ Docling ─────────────────────────────────────
    struct_raw, rows = build_struct_raw(doc, pdf_path)

    # ── BƯỚC 1.6: Tìm heading bị Docling nhận nhầm + thu thập tọa độ elements ─
    def bold_not_preceded_by_normal(page, bbox, page_height) -> bool:
        rect = fitz.Rect(bbox.l, page_height - bbox.t, bbox.r, page_height - bbox.b)
        blocks = page.get_text("dict", clip=rect)["blocks"]
        for b in blocks:
            for line in b.get("lines", []):
                spans = [s for s in line.get("spans", []) if s["text"].strip()]
                found_bold = False
                for span in spans:
                    if is_bold(span):
                        found_bold = True
                    else:
                        if not found_bold:
                            return False
        return True

    _SUSPECT_LABELS = {DocItemLabel.TEXT, DocItemLabel.LIST_ITEM}
    _pdf = fitz.open(pdf_path)
    suspect_rows   = []
    element_coords = []

    for item, _level in doc.iterate_items():
        if item.label in (
            DocItemLabel.TEXT, DocItemLabel.FORMULA, DocItemLabel.PICTURE,
            DocItemLabel.TABLE, DocItemLabel.LIST_ITEM, DocItemLabel.CODE,
        ) and item.prov:
            prov = item.prov[0]
            bbox = prov.bbox
            # Thành thế này:
            page_obj = _pdf[prov.page_no - 1]
            info = dominant_span_info(page_obj, bbox, page_obj.rect.height)   # ← đọc font ngay tại đây

            element_coords.append({
                "type"     : item.label.value,
                "page"     : prov.page_no,
                "bbox_l"   : round(bbox.l, 1),
                "bbox_t"   : round(bbox.t, 1),
                "bbox_r"   : round(bbox.r, 1),
                "bbox_b"   : round(bbox.b, 1),
                "text"     : getattr(item, "text", "")[:120],
                "font_name": info["font"] if info else "unknown",       # ← lưu luôn
                "base_font": info["base_font"] if info else "unknown",  # ← lưu luôn (tên sạch)
                "font_size": info["size"] if info else 0,               # ← lưu luôn
            })

        if item.label not in _SUSPECT_LABELS or not item.prov: continue
        raw_text = getattr(item, "text", "")
        if "\n" in raw_text or len(raw_text) > 200: continue
        prov = item.prov[0]
        page = _pdf[prov.page_no - 1]
        bbox = prov.bbox

        rect = fitz.Rect(bbox.l, page.rect.height - bbox.t, bbox.r, page.rect.height - bbox.b)
        blocks = page.get_text("dict", clip=rect)["blocks"]
        if sum(len(b.get("lines", [])) for b in blocks) != 1: continue

        info = dominant_span_info(page, bbox, page.rect.height)
        if info is None or not info["bold"]: continue
        if (info["base_font"], info["size"]) not in heading_signatures: continue
        if not bold_not_preceded_by_normal(page, bbox, page.rect.height): continue

        suspect_rows.append({
            "label": item.label.value, "page": prov.page_no, "font": info["font"],
            "base_font": info["base_font"], "size": info["size"], "text": raw_text[:80],
            "bbox": (round(bbox.l,1), round(bbox.t,1), round(bbox.r,1), round(bbox.b,1)),
        })

    _pdf.close()

    # Ghi đè lại element_coords bằng danh sách thật sự (đã loại bỏ suspect)
    element_coords = filter_suspects_from_elements(suspect_rows, element_coords, tolerance=2.0)

    # HÀM CHUYỂN TEXT -> CODE
    element_coords = convert_monospace_text_to_code(element_coords, pdf_path)

    # Cắt các bức ảnh bị dính Code làm đôi
    element_coords = split_picture_containing_code(element_coords, pdf_path)


    # ── BƯỚC 1.7: Gộp suspect vào rows ───────────────────────────────────────
    size_to_level = {r["font_size"]: r["level"] for r in rows}
    normalized = []
    for r in rows:
        normalized.append({
            "level": r["level"], "text": r["text"], "page": r["page"],
            "font_size": r["font_size"], "bbox_l": r["bbox_l"], "bbox_t": r["bbox_t"],
            "bbox_r": r["bbox_r"], "bbox_b": r["bbox_b"], "source": "docling",
        })

    for r in suspect_rows:
        level = size_to_level.get(r["size"])
        if level is None:
            known = sorted(size_to_level.items(), key=lambda x: x[0])
            level = 1
            for sz, lv in known:
                if r["size"] >= sz: level = lv
        l, t, r_, b = r["bbox"]
        normalized.append({
            "level": level, "text": r["text"], "page": r["page"], "font_size": r["size"],
            "bbox_l": l, "bbox_t": t, "bbox_r": r_, "bbox_b": b, "source": "suspect",
        })

    seen, deduped = set(), []
    for r in normalized:
        key = (r["page"], r["text"].strip().lower()[:60])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    struct_merged = sorted(deduped, key=lambda r: (r["page"], -r["bbox_t"]))

    # Thêm font_name cho tất cả các heading
    struct_merged = enrich_font_name(struct_merged, pdf_path)

    struct_merged, removed_headings = filter_monospace_headings(struct_merged, element_coords, pdf_path)

    element_coords, removed_headings_log = resolve_removed_headings(
        struct_merged, removed_headings, element_coords
    )

    # Sửa các TABLE bị nhận nhầm từ PICTURE (dựa vào caption "hình"/"figure")
    element_coords, fixed_table_to_picture = fix_tables_misidentified_as_pictures(element_coords, doc)

    # Gộp các picture bị tách rời theo toạ độ (cùng mốc, không vật cản chen giữa)
    element_coords, merged_pictures_info = merge_pictures_by_coordinates(
        pdf_path, element_coords, struct_merged, doc
    )

    # Thêm field "caption" (None mặc định) cho mọi entry trong element_coords
    element_coords = add_caption_field_to_element_coords(element_coords, doc)

    # ── BƯỚC 2.2 & 2.3: Chạy luồng Mục Lục (TOC) ────────────────────────────
    real_heading_muc_luc = extract_toc_headings(pdf_path)

    if real_heading_muc_luc:
        idx_toc, no_idx_toc, grouped_heading = process_toc_v2(real_heading_muc_luc)
        toc_heading_level, toc_tree, _ = assign_levels_and_build_tree(grouped_heading, real_heading_muc_luc, struct_merged)

        toc_items_list = []
        for sig, items in grouped_heading.items():
            toc_items_list.extend(items)
        toc_items_list.sort(key=lambda x: x.get("original_order", 0))
    else:
        toc_heading_level, toc_tree = [], ""
        toc_items_list = []

    bookmark_tree = extract_bookmark_tree(pdf_path)

    if bookmark_tree:
        import difflib
        real_heading_muc_luc_level = []
        last_matched_idx = 0

        for item in bookmark_tree:
            norm_title = "".join(str(item["title"]).split()).lower()
            best_idx, best_ratio, best_k = "", 0.0, last_matched_idx
            window_end = min(last_matched_idx + 15, len(toc_items_list))

            for k in range(last_matched_idx, window_end):
                toc_item = toc_items_list[k]
                norm_toc_text = "".join(str(toc_item.get("text", "")).split()).lower()
                ratio = difflib.SequenceMatcher(None, norm_title, norm_toc_text).ratio()
                if ratio > best_ratio:
                    best_ratio, best_idx, best_k = ratio, toc_item.get("extracted_index", ""), k

            if best_ratio >= 0.5:
                idx = best_idx
                last_matched_idx = best_k + 1
            else:
                idx = ""

            real_heading_muc_luc_level.append({
                "text": item["title"], "level": item["level"],
                "page_num": item["page"], "extracted_index": idx,
            })

        tree_lines = ["    " * (item["level"] - 1) + "- " + item["title"] for item in bookmark_tree]
        heading_muc_luc_tree = "\n".join(tree_lines)
    else:
        real_heading_muc_luc_level = toc_heading_level
        heading_muc_luc_tree = toc_tree



    # ── PHẦN 3: ĐỒNG BỘ XUỐNG VĂN BẢN ───────────────────────────────────────
    struct_merged = assign_levels_to_struct_merged(struct_merged, real_heading_muc_luc_level)

    heading_con_sot_giua_2level = get_missing_level_blocks(struct_merged)

    # Gán level tự động cho các khối bị sót
    assign_levels_for_missing_blocks(heading_con_sot_giua_2level)

    # In kết quả level cuối cùng sau khi đã khớp bookmark và xử lý các khối bị sót.
    print("\n===== LEVEL CUỐI CÙNG CỦA CÁC HEADING =====")
    for position, heading in enumerate(struct_merged, start=1):
        print(
            f"[{position:04d}] Level {heading.get('level')} | "
            f"Trang {heading.get('page')} | {heading.get('text', '').strip()}"
        )

    # ── BÁO CÁO NHANH GỌN LẸ ────────────────────────────────────────────────
    print(f" ĐÃ XỬ LÝ XONG: Tìm thấy {len(struct_merged)} heading và lấp đầy {len(heading_con_sot_giua_2level)} khối bị sót.")

    return struct_merged, real_heading_muc_luc_level, heading_muc_luc_tree, element_coords, heading_con_sot_giua_2level, removed_headings_log


def process_document(
    pdf_path,
    doc,
    document_id,
    *,
    supabase_client=None,
    image_output_dir="cropped_images",
):
    """Ghép đúng thứ tự xử lý trong cell worker cũ, không đổi thuật toán."""
    (
        struct_merged,
        real_heading_muc_luc_level,
        heading_muc_luc_tree,
        element_coords,
        heading_con_sot_giua_2level,
        removed_headings_log,
    ) = find_heading(pdf_path, doc)

    element_coords = filter_elements_after_toc(element_coords, struct_merged)
    element_coords = assign_heading_paths(element_coords, struct_merged)
    element_coords = assign_context_snippets(element_coords, max_chars=300)
    element_coords = extract_full_table_text(element_coords, doc)
    element_coords = crop_and_upload_images(
        element_coords,
        pdf_path,
        output_dir=image_output_dir,
        supabase_client=supabase_client,
        doc_ai_id=document_id,
    )
    chunks = package_chunks(
        element_coords,
        struct_merged=struct_merged,
        document_id=document_id,
    )
    diagnostics = {
        "real_heading_muc_luc_level": real_heading_muc_luc_level,
        "heading_muc_luc_tree": heading_muc_luc_tree,
        "heading_con_sot_giua_2level": heading_con_sot_giua_2level,
        "removed_headings_log": removed_headings_log,
    }
    return chunks, diagnostics
