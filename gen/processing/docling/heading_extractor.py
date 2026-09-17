"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""

import fitz

from docling_core.types.doc import SectionHeaderItem

from collections import Counter

def extract_chars_in_bbox(page, rect):
    d = page.get_text("rawdict", clip=rect)
    chars = []
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span["size"]
                for ch in span.get("chars", []):
                    c = ch["c"]
                    if c.strip() == "" and c != " ":
                        continue
                    x0, y0, x1, y1 = ch["bbox"]
                    origin_x, origin_y = ch["origin"]
                    chars.append({
                        "char": c,
                        "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                        "origin_x": origin_x,
                        "origin_y": origin_y,
                        "size": size,
                    })
    return chars

def classify_track(chars, baseline_tolerance=1.5):
    if not chars:
        return chars
    rounded = [round(c["origin_y"]) for c in chars]
    main_baseline = Counter(rounded).most_common(1)[0][0]
    for c in chars:
        dy = c["origin_y"] - main_baseline
        if abs(dy) <= baseline_tolerance:
            c["track"] = "main"
        elif dy < 0:
            c["track"] = "sup"
        else:
            c["track"] = "sub"
    return chars

def chars_to_text(chars, mark_sup_sub=False, space_gap_ratio=0.25):
    if not chars:
        return ""
    chars_sorted = sorted(chars, key=lambda c: c["x0"])

    out = []
    prev = None
    for c in chars_sorted:
        if prev is not None:
            gap = c["x0"] - prev["x1"]
            # Nếu khoảng trống giữa 2 ký tự đủ lớn so với size font → coi là có space
            threshold = prev["size"] * space_gap_ratio
            if gap > threshold and c["char"] != " " and prev["char"] != " ":
                out.append(" ")
        out.append(c["char"])
        prev = c
    return "".join(out)

def _wrap(s, track):
    if track == "sup":
        return f"^{{{s}}}"
    if track == "sub":
        return f"_{{{s}}}"
    return s

def get_heading_text_from_bbox(page, rect, mark_sup_sub=False):
    chars = extract_chars_in_bbox(page, rect)
    chars = classify_track(chars)
    text = chars_to_text(chars, mark_sup_sub=mark_sup_sub)
    dominant_size = None
    if chars:
        size_count = Counter()
        for c in chars:
            size_count[round(c["size"], 1)] += 1
        dominant_size = size_count.most_common(1)[0][0]
    return text, dominant_size, chars

def build_struct_raw(doc, pdf_path, mark_sup_sub=False):
    pdf = fitz.open(pdf_path)
    rows = []

    for item, level in doc.iterate_items():
        if not isinstance(item, SectionHeaderItem):
            continue
        if not item.prov:
            continue

        prov = item.prov[0]
        page_no = prov.page_no
        bbox = prov.bbox
        page = pdf[page_no - 1]
        page_height = page.rect.height

        # Docling bbox: gốc dưới-trái (PDF coords) -> đổi sang PyMuPDF (gốc trên-trái)
        rect = fitz.Rect(
            bbox.l,
            page_height - bbox.t,
            bbox.r,
            page_height - bbox.b
        )

        text, dominant_size, chars = get_heading_text_from_bbox(
            page, rect, mark_sup_sub=mark_sup_sub
        )

        rows.append({
            "level"        : item.level,
            "text"         : text,
            "page"         : page_no,
            "font_size"    : dominant_size,
            "bbox_l"       : round(bbox.l, 1),
            "bbox_t"       : round(bbox.t, 1),
            "bbox_r"       : round(bbox.r, 1),
            "bbox_b"       : round(bbox.b, 1),
            "chars_detail" : chars,   # debug: xem từng ký tự + track nếu cần
        })

    # ── In ra bảng + lưu struct_raw ──────────────────────────────────────────
    print(f"{'H':<4} {'Trang':<6} {'Size':<6} {'Left_Top':<14} {'Left_Bot':<14} {'Text'}")
    print("-" * 90)

    struct_raw = []
    for r in rows:
        indent = "  " * (r["level"] - 1)
        left_top = f"({r['bbox_l']}, {r['bbox_t']})"
        left_bot = f"({r['bbox_l']}, {r['bbox_b']})"
        line = (f"H{r['level']:<3} {r['page']:<6} {str(r['font_size']):<6} "
                f"{left_top:<14} {left_bot:<14} {indent}{r['text']}")
        print(line)
        struct_raw.append({
            "level"        : r["level"],
            "page"         : r["page"],
            "font_size"    : r["font_size"],
            "left_top"     : (r["bbox_l"], r["bbox_t"]),
            "left_bot"     : (r["bbox_l"], r["bbox_b"]),
            "text"         : r["text"],
            "chars_detail" : r["chars_detail"],
        })

    print(f"\nĐã lưu {len(struct_raw)} heading vào struct_raw")
    return struct_raw, rows

import fitz

import re

from collections import defaultdict

from docling_core.types.doc import SectionHeaderItem, TextItem, DocItemLabel

def is_bold(span: dict) -> bool:
    if span["flags"] & 16:
        return True
    fname = span["font"].lower()
    return any(kw in fname for kw in ("bold", "black", "heavy", "demi", "semibold"))

def base_font(font_name: str) -> str:
    return re.sub(r"[-,]?(bold|italic|regular|roman|light|medium|black|heavy|demi|semibold|oblique).*",
                  "", font_name, flags=re.IGNORECASE).strip()

def dominant_span_info(page, bbox, page_height):
    rect = fitz.Rect(bbox.l, page_height - bbox.t, bbox.r, page_height - bbox.b)
    best = None
    best_len = -1
    for b in page.get_text("dict", clip=rect)["blocks"]:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                t = span["text"].strip()
                if not t:
                    continue
                if len(t) > best_len:
                    best_len = len(t)
                    best = span
    if best is None:
        return None
    return {
        "font"     : best["font"],
        "base_font": base_font(best["font"]),
        "size"     : round(best["size"], 1),
        "bold"     : is_bold(best),
    }

def get_bold_headings(doc, pdf_path):
    pdf = fitz.open(pdf_path)
    heading_signatures = set()
    heading_rows = []

    for item, level in doc.iterate_items():
        if item.label not in (DocItemLabel.TITLE, DocItemLabel.SECTION_HEADER):
            continue
        if not item.prov:
            continue
        prov  = item.prov[0]
        bbox  = prov.bbox
        page  = pdf[prov.page_no - 1]
        info  = dominant_span_info(page, bbox, page.rect.height)
        if info is None or not info["bold"]:
            continue

        sig = (info["base_font"], info["size"])
        heading_signatures.add(sig)
        heading_rows.append({
            "label"    : item.label.value,
            "page"     : prov.page_no,
            "font"     : info["font"],
            "base_font": info["base_font"],
            "size"     : info["size"],
            "bbox_l"   : round(bbox.l, 1),
            "bbox_t"   : round(bbox.t, 1),
            "bbox_b"   : round(bbox.b, 1),
            "text"     : getattr(item, "text", "")[:80],
        })

    print(f"=== HEADING ĐẬM ({len(heading_rows)} dòng) ===")

    heading_raw_elements = []

    for r in heading_rows:
        heading_raw_elements.append({
            "label"    : r["label"],
            "page"     : r["page"],
            "size"     : r["size"],
            "left_top" : (r["bbox_l"], r["bbox_t"]),
            "left_bot" : (r["bbox_l"], r["bbox_b"]),
            "font"     : r["font"],
            "base_font": r["base_font"],
            "text"     : r["text"],
        })

    print(f"Signatures cần khớp: {heading_signatures}")
    print(f"Đã lưu {len(heading_raw_elements)} heading vào heading_raw_elements")

    return heading_raw_elements, heading_signatures

import fitz

from docling_core.types.doc import DocItemLabel

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
            element_coords.append({
                "type": item.label.value, "page": prov.page_no,
                "bbox_l": round(bbox.l, 1), "bbox_t": round(bbox.t, 1),
                "bbox_r": round(bbox.r, 1), "bbox_b": round(bbox.b, 1),
                "text": getattr(item, "text", "")[:120],
            })

        if item.label not in _SUSPECT_LABELS or not item.prov:
            continue
        raw_text = getattr(item, "text", "")
        if "\n" in raw_text or len(raw_text) > 200:
            continue

        prov = item.prov[0]
        page = _pdf[prov.page_no - 1]
        bbox = prov.bbox
        rect = fitz.Rect(bbox.l, page.rect.height - bbox.t, bbox.r, page.rect.height - bbox.b)
        blocks = page.get_text("dict", clip=rect)["blocks"]
        if sum(len(b.get("lines", [])) for b in blocks) != 1:
            continue

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
    return element_coords, suspect_rows

def merge_and_normalize_headings(rows, suspect_rows):
    """Gộp, gán level cho heading rác, loại trùng và sắp xếp"""
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

    return sorted(deduped, key=lambda r: (r["page"], -r["bbox_t"]))
