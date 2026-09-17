"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""

from pypdf import PdfReader

def read_bookmarks(outline_items, reader, level=1):
    """Duyệt đệ quy danh sách bookmark, hỗ trợ lồng nhiều cấp."""
    result = []
    for item in outline_items:
        if isinstance(item, list):
            result.extend(read_bookmarks(item, reader, level + 1))
        else:
            title = item.title.strip() if item.title else "(không có tiêu đề)"
            page_num = None
            try:
                page_num = reader.get_destination_page_number(item) + 1
            except Exception:
                pass
            result.append({"level": level, "title": title, "page": page_num})
    return result

def extract_bookmark_tree(pdf_path):
    """Mở PDF và trích xuất toàn bộ bookmark thành cây phân cấp."""
    reader = PdfReader(pdf_path)

    if not reader.outline:
        print(" File PDF này không có bookmark.")
        print("   → Hãy dùng code extract_toc_tree (đọc từ trang Mục lục) thay thế.")
        return []

    print(f" Tìm thấy bookmark — Tổng số trang PDF: {len(reader.pages)}\n")
    return read_bookmarks(reader.outline, reader, level=1)

def print_bookmark_tree(tree):
    """In cây bookmark ra màn hình."""
    if not tree:
        return
    print("=" * 55)
    print(" CẤU TRÚC MỤC LỤC (từ Bookmark)")
    print("=" * 55)
    for item in tree:
        indent   = "  " * (item["level"] - 1)
        dash     = "─" * item["level"]
        page_str = f"  →  trang {item['page']}" if item["page"] else ""
        print(f"{indent}{dash} {item['title']}{page_str}")
    print("=" * 55)
    print(f"Tổng cộng: {len(tree)} mục")

def export_to_csv(tree, output_path="bookmark_toc.csv"):
    """Xuất kết quả ra file CSV."""
    import csv
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["level", "title", "page"])
        writer.writeheader()
        writer.writerows(tree)
    print(f" Đã xuất CSV: {output_path}")
    files.download(output_path)

def export_to_excel(tree, output_path="bookmark_toc.xlsx"):
    """Xuất kết quả ra file Excel."""
    import pandas as pd
    df = pd.DataFrame(tree)
    df.columns = ["Cấp độ", "Tiêu đề", "Số trang"]
    df.to_excel(output_path, index=False)
    print(f" Đã xuất Excel: {output_path}")
    files.download(output_path)

import re

import unicodedata

import pdfplumber

from collections import Counter

TOC_KEYWORDS = ["mục lục", "table of contents", "contents", "content", "m ục l ục", "m u c l u c", "mục  lục", "m ục  l ục"]

TOP_MARGIN = 70

BOT_MARGIN = 60

FONT_SIZE_DIFF_THRESHOLD = 1.5

def clean_toc_text(text):
    if not text:
        return ""
    text = re.sub(r'[\s\.\-\–\_,\:]+$', '', text)
    return text.strip()

def normalize_toc_line(text):
    text = unicodedata.normalize('NFC', text.strip().lower())
    text = " ".join(text.split())
    return text

def is_roman(s):
    if not s: return False
    return bool(re.match(r'^(X{0,3})(IX|IV|V?I{0,3})$', s))

def is_arabic(s):
    return bool(re.fullmatch(r'\d+', s.strip()))

def is_roman_strict(s):
    if not s: return False
    return bool(re.match(r'^(X{0,3})(IX|IV|V?I{0,3})$', s))

def type_of_token(w):
    if re.match(r'^\d+$', w): return 'ARABIC'
    if is_roman_strict(w): return 'ROMAN'
    if len(w) == 1 and w.isupper(): return 'LETTER'
    return 'UNKNOWN'

def is_so(w):
    w = w.strip('()')
    w = re.sub(r'[:.]+$', '', w)
    if not w: return False
    parts = w.split('.')
    for p in parts:
        if not (re.match(r'^\d+$', p) or (len(p)==1 and p.isupper()) or is_roman_strict(p)):
            return False
    return True

def get_index_and_group(line):
    words = line.strip().split()
    if not words: return None, None

    w0_clean = re.sub(r'[:.]+$', '', words[0])
    w1_clean = re.sub(r'[:.]+$', '', words[1]) if len(words) > 1 else ''

    idx = None
    if len(words) > 1 and not is_so(w0_clean) and is_so(w1_clean):
        idx = w0_clean + ' ' + w1_clean
    elif is_so(w0_clean):
        idx = w0_clean

    if not idx:
        return None, None

    idx_words = idx.split()
    if len(idx_words) == 2:
        group = f'PREFIX_{idx_words[0]}_{type_of_token(idx_words[1])}'
    else:
        parts = idx_words[0].split('.')
        group = '.'.join(type_of_token(p) for p in parts)

    return idx, group

def get_body_lines(page, top_margin, bot_margin):
    h = page.height
    w = page.width

    cropped = page.crop((0, top_margin, w, h - bot_margin))
    words = cropped.extract_words(
        extra_attrs=["size", "fontname"],
        y_tolerance=3,
    )
    if not words:
        return []

    lines = []
    current_line = [words[0]]
    for word in words[1:]:
        if abs(word['top'] - current_line[0]['top']) < 3:
            current_line.append(word)
        else:
            lines.append(current_line)
            current_line = [word]
    lines.append(current_line)

    result = []
    for line in lines:
        line_sorted = sorted(line, key=lambda w: w['x0'])
        full_text = " ".join(w['text'] for w in line_sorted).strip()

        page_num = None
        page_num_type = None
        heading_text_str = full_text

        m_dots_arabic = re.search(r'(.*?)(?:[\.\-\_]{3,}\s*|\s{4,})(\d+)\s*$', full_text)
        m_dots_roman  = re.search(r'(.*?)(?:[\.\-\_]{3,}\s*|\s{4,})([ivxlcdmIVXLCDM]{1,6})\s*$', full_text)

        if m_dots_arabic:
            page_num          = int(m_dots_arabic.group(2))
            page_num_type     = 'arabic'
            heading_text_str  = m_dots_arabic.group(1).strip()
        elif m_dots_roman:
            page_num          = m_dots_roman.group(2)
            page_num_type     = 'roman'
            heading_text_str  = m_dots_roman.group(1).strip()
        else:
            rightmost  = line_sorted[-1]
            token      = rightmost['text'].strip()

            if len(line_sorted) > 1:
                token_clean = re.sub(r'^[\.\-\_]+', '', token)
                if is_arabic(token_clean):
                    page_num          = int(token_clean)
                    page_num_type     = 'arabic'
                    heading_text_str  = " ".join(w['text'] for w in line_sorted[:-1]).strip()
                elif is_roman(token_clean):
                    page_num          = token_clean
                    page_num_type     = 'roman'
                    heading_text_str  = " ".join(w['text'] for w in line_sorted[:-1]).strip()

        heading_text_str = clean_toc_text(heading_text_str)

        heading_words = []
        if page_num is not None and len(line_sorted) > 1:
            last_text = line_sorted[-1]['text']
            if str(page_num) in last_text:
                heading_words = line_sorted[:-1]
            else:
                heading_words = line_sorted
        else:
            heading_words = line_sorted

        heading_words_clean = []
        for w in heading_words:
            if re.fullmatch(r'[\.\-\_]+', w['text']):
                continue
            heading_words_clean.append(w)

        if not heading_words_clean:
            heading_words_clean = heading_words

        if len(heading_words_clean) > 0:
            x0       = min(w['x0'] for w in heading_words_clean)
            y0       = heading_words_clean[0]['top']
            fonts    = [w.get("fontname", "") for w in heading_words_clean if w.get("fontname")]
            fontname = Counter(fonts).most_common(1)[0][0] if fonts else "unknown"

            idx, _ = get_index_and_group(heading_text_str)
            if idx:
                idx_word_count    = len(idx.split())
                after_index_words = heading_words_clean[idx_word_count:]
                index_words       = heading_words_clean[:idx_word_count]

                if after_index_words:
                    avg_size = after_index_words[0].get('size', 0)
                else:
                    sizes    = [w.get('size', 0) for w in heading_words_clean if w.get('size', 0) > 0]
                    avg_size = sum(sizes) / len(sizes) if sizes else 0

                index_size = index_words[0].get('size', 0) if index_words else avg_size
            else:
                avg_size   = heading_words_clean[0].get('size', 0)
                index_size = avg_size

        else:
            x0         = min(w['x0'] for w in line_sorted)
            y0         = line_sorted[0]['top']
            avg_size   = 0
            index_size = 0
            fontname   = "unknown"

        is_bold = "bold" in fontname.lower()

        result.append({
            "text":          heading_text_str,
            "x0":            x0,
            "y0":            y0,
            "avg_size":      avg_size,
            "index_size":    index_size,
            "fontname":      fontname,
            "is_bold":       is_bold,
            "font_weight":   700 if is_bold else 400,
            "page_num":      page_num,
            "page_num_type": page_num_type,
        })
    return result

def is_toc_title(line):
    text_clean = " ".join(line['text'].strip().lower().split())
    text_clean = unicodedata.normalize('NFC', text_clean)
    for kw in TOC_KEYWORDS:
        kw_norm = unicodedata.normalize('NFC', kw.lower())
        if kw_norm in text_clean:
            return True
    return False

def extract_toc_headings(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:

        toc_start_page     = None
        toc_start_line_idx = None

        for page_idx, page in enumerate(pdf.pages):
            if page_idx > 20:
                break
            lines = get_body_lines(page, TOP_MARGIN, BOT_MARGIN)
            for i, line in enumerate(lines):
                if is_toc_title(line):
                    toc_start_page     = page_idx
                    toc_start_line_idx = i + 1
                    print(f" Tìm thấy mục lục ở trang {page_idx + 1}, dòng: \"{line['text']}\"")
                    break
            if toc_start_page is not None:
                break

        if toc_start_page is None:
            print(" Không tìm thấy mục lục trong file này.")
            return []

        all_lines = []
        for page_idx in range(
            toc_start_page,
            min(toc_start_page + 10, len(pdf.pages))
        ):
            page_lines = get_body_lines(pdf.pages[page_idx], TOP_MARGIN, BOT_MARGIN)
            start_idx  = toc_start_line_idx if page_idx == toc_start_page else 0
            all_lines.extend(page_lines[start_idx:])

        toc_lines       = []
        toc_index       = {}
        last_valid_page = None

        for i, line in enumerate(all_lines):
            current_page      = line['page_num']
            current_page_type = line['page_num_type']

            cleaned_text = clean_toc_text(line['text'])
            if not cleaned_text:
                continue

            text_norm = normalize_toc_line(cleaned_text)
            if not text_norm:
                continue

            if current_page_type == 'arabic':
                if last_valid_page is not None and current_page < last_valid_page:
                    is_end = True
                    lookahead_count = 0
                    for j in range(i + 1, len(all_lines)):
                        next_page      = all_lines[j]['page_num']
                        next_page_type = all_lines[j]['page_num_type']
                        if next_page_type == 'arabic':
                            lookahead_count += 1
                            if next_page >= last_valid_page:
                                is_end = False
                                break
                            if lookahead_count >= 2:
                                break
                    if is_end:
                        print(f" Kết thúc TOC do số trang lùi "
                              f"(từ {last_valid_page} → {current_page}) "
                              f"tại: \"{cleaned_text}\"")
                        break
                last_valid_page = current_page

            elif current_page is None:
                if last_valid_page is not None:
                    has_future_page = False
                    for j in range(i + 1, min(i + 5, len(all_lines))):
                        next_page      = all_lines[j]['page_num']
                        next_page_type = all_lines[j]['page_num_type']
                        if next_page_type == 'arabic' and next_page >= last_valid_page:
                            has_future_page = True
                            break
                    if not has_future_page:
                        print(f" Kết thúc TOC do hết số trang tiếp nối, "
                              f"dừng trước: \"{cleaned_text}\"")
                        break

            if text_norm not in toc_index:
                toc_index[text_norm] = line['avg_size']
            else:
                toc_size     = toc_index[text_norm]
                curr_size    = line['avg_size']
                size_differs = (
                    toc_size > 0 and curr_size > 0
                    and abs(curr_size - toc_size) >= FONT_SIZE_DIFF_THRESHOLD
                )
                if size_differs:
                    print(f" Kết thúc TOC do lặp nội dung chính "
                          f"(font size khác) tại: \"{cleaned_text}\"")
                    break

            line['text'] = cleaned_text
            toc_lines.append(line)

        return toc_lines

import re

from collections import defaultdict

def is_roman(s):
    if not s: return False
    return bool(re.match(r'^(X{0,3})(IX|IV|V?I{0,3})$', s))

def type_of_token(w):
    if re.match(r'^\d+$', w): return 'TOKEN'
    if is_roman(w): return 'TOKEN'
    if len(w) == 1 and w.isupper(): return 'TOKEN'
    return 'UNKNOWN'

def is_so(w):
    w = w.strip('()')
    w = re.sub(r'[:.]+$', '', w)
    if not w: return False
    parts = w.split('.')
    for p in parts:
        if not (re.match(r'^\d+$', p) or (len(p)==1 and p.isupper()) or is_roman(p)):
            return False
    return True

def get_index_and_group(line):
    words = line.strip().split()
    if not words: return None, None

    w0_clean = re.sub(r'[:.]+$', '', words[0])
    w1_clean = re.sub(r'[:.]+$', '', words[1]) if len(words) > 1 else ''

    idx = None
    if len(words) > 1 and not is_so(w0_clean) and is_so(w1_clean):
        idx = w0_clean + ' ' + w1_clean
    elif is_so(w0_clean):
        idx = w0_clean

    if not idx: return None, None

    idx_words = idx.split()
    if len(idx_words) == 2:
        group = f'PREFIX_{idx_words[0]}_{type_of_token(idx_words[1])}'
    else:
        parts = idx_words[0].split('.')
        group = '.'.join(type_of_token(p) for p in parts)

    return idx, group

def group_all_headings(heading_list):
    indexed_groups  = defaultdict(list)
    no_index_groups = defaultdict(list)

    if isinstance(heading_list, str): heading_list = [heading_list]
    elif isinstance(heading_list, dict): heading_list = [heading_list]

    for i, original_item in enumerate(heading_list):
        item = {'text': original_item} if isinstance(original_item, str) else original_item.copy()
        item['original_order'] = i

        text = item.get('text', '')
        if not text: continue

        idx, group_signature = get_index_and_group(text)

        if idx:
            item['extracted_index'] = idx
            indexed_groups[group_signature].append(item)
        else:
            left_margin    = item.get('x0', 0)
            font_size      = item.get('avg_size', 0)
            font_name      = item.get('fontname', 'UNKNOWN')

            rounded_margin = round(left_margin, 1)
            rounded_size   = round(font_size, 1)

            no_idx_sig     = f"NO_INDEX_Margin({rounded_margin})_Size({rounded_size})_Font({font_name})"
            no_index_groups[no_idx_sig].append(item)

    return indexed_groups, no_index_groups

def check_hierarchy(indexed_groups, no_index_groups, margin_tolerance=5):
    # Dấu hiệu 2: Bất kỳ cặp no_index nào CÙNG LỀ mà KHÁC font/size -> KHÔNG phân cấp
    no_idx_items_all = []
    for items in no_index_groups.values():
        no_idx_items_all.extend(items)

    for i, item_a in enumerate(no_idx_items_all):
        for item_b in no_idx_items_all[i+1:]:
            if abs(item_a.get('x0', 0) - item_b.get('x0', 0)) <= margin_tolerance:
                if (item_a.get('fontname') != item_b.get('fontname') or
                    round(item_a.get('avg_size', 0), 1) != round(item_b.get('avg_size', 0), 1)):
                    return False

    # Mặc định: có phân bậc
    return True

def group_by_font_and_size(indexed_groups, no_index_groups):
    merged_groups = defaultdict(list)
    def add_to_merged(groups_dict):
        for sig, items in groups_dict.items():
            for item in items:
                fontname = item.get('fontname', 'UNKNOWN')
                avg_size = round(item.get('avg_size', 0), 1)
                merged_groups[f"Font({fontname})_Size({avg_size})"].append(item)
    add_to_merged(indexed_groups)
    add_to_merged(no_index_groups)
    return dict(merged_groups)

def merge_fake_indexed_to_no_index(indexed_groups, no_index_groups, margin_tolerance=5):
    def is_no_dot(group_sig):
        if group_sig == 'TOKEN': return True   # Thay cho ARABIC/ROMAN/LETTER
        if re.match(r'^PREFIX_\w+_TOKEN$', group_sig): return True
        return False

    remaining_indexed = {}
    for group_sig, indexed_items in indexed_groups.items():
        if not is_no_dot(group_sig):
            remaining_indexed[group_sig] = indexed_items
            continue

        unmatched = []
        for item in indexed_items:
            margin   = item.get('x0', 0)
            fontname = item.get('fontname', 'UNKNOWN')
            avg_size = round(item.get('avg_size', 0), 1)

            matched_sig = None
            for no_idx_sig, no_items in no_index_groups.items():
                if not no_items: continue
                rep_margin = no_items[0].get('x0', 0)
                if (abs(margin - rep_margin) <= margin_tolerance
                        and fontname == no_items[0].get('fontname', 'UNKNOWN')
                        and avg_size == round(no_items[0].get('avg_size', 0), 1)):
                    matched_sig = no_idx_sig
                    break

            if matched_sig:
                item['_merged_by_step5'] = True   # ← Đánh dấu: Bước 5 đã xác nhận là giả
                no_index_groups[matched_sig].append(item)
            else:
                unmatched.append(item)

        if unmatched: remaining_indexed[group_sig] = unmatched

    return remaining_indexed, no_index_groups

def split_mixed_category_groups(indexed_groups, no_index_groups):
    def get_item_category(item):
        text = item.get('text', '')
        idx, group_sig = get_index_and_group(text)
        if not idx: return 'NO_INDEX', None
        if group_sig.startswith('PREFIX_'): return 'PREFIX', group_sig
        if '.' in group_sig: return 'MULTI_LEVEL', group_sig
        if group_sig == 'TOKEN': return 'SIMPLE', group_sig   # Thay cho 3 cái cũ
        return 'UNKNOWN', group_sig

    new_no_index = {}
    for sig, items in no_index_groups.items():
        no_index_items = []
        indexed_by_cat = defaultdict(list)

        for item in items:
            cat, _ = get_item_category(item)
            if cat == 'NO_INDEX': no_index_items.append(item)
            else: indexed_by_cat[cat].append(item)

        if len(indexed_by_cat) <= 1:
            new_no_index[sig] = items
            continue

        first_order = {c: min(i.get('original_order', float('inf')) for i in l) for c, l in indexed_by_cat.items()}
        sorted_cats = sorted(indexed_by_cat.keys(), key=lambda c: first_order[c])
        primary_cat = sorted_cats[0]
        new_no_index[sig] = no_index_items + indexed_by_cat[primary_cat]

        for cat in sorted_cats[1:]:
            for item in indexed_by_cat[cat]:
                item['_is_evicted'] = True
                item['_evicted_from'] = sig

                _, orig_sig = get_index_and_group(item.get('text', ''))
                if orig_sig:
                    if orig_sig not in indexed_groups: indexed_groups[orig_sig] = []
                    indexed_groups[orig_sig].append(item)

    return indexed_groups, new_no_index

def get_hierarchy_level(group_sig):
    if group_sig in ('LETTER', 'ROMAN', 'ARABIC') or group_sig.startswith('PREFIX_'): return 1
    if '.' in group_sig: return 2
    return 99

def execute_reverse_hierarchy_check(indexed_groups, no_index_groups):
    # Gốc so: LẤY TỪ CẢ HAI RỔ — bất kỳ item nào còn extracted_index đều dùng làm mốc
    all_indexed_entries = []
    for sig, items in indexed_groups.items():
        for item in items:
            all_indexed_entries.append((sig, item))

    # Thêm các item trong no_index mà vẫn còn chỉ số gốc
    for sig, items in no_index_groups.items():
        for item in items:
            if item.get('extracted_index'):
                _, orig_sig = get_index_and_group(item.get('text', ''))
                if orig_sig:
                    all_indexed_entries.append((orig_sig, item))

    fakes = []
    for sig_loai, item in all_indexed_entries:
        if not item.get('_is_evicted'): continue

        bac_loai = get_hierarchy_level(sig_loai)
        le_loai = item.get('x0', 0)

        is_fake = False
        for sig_valid, valid_item in all_indexed_entries:
            if valid_item is item or valid_item.get('_is_evicted'): continue

            bac_valid = get_hierarchy_level(sig_valid)
            le_valid = valid_item.get('x0', 0)

            if bac_loai <= bac_valid and le_loai > le_valid:
                is_fake = True
                break

        if is_fake: fakes.append((sig_loai, item))

    for sig_loai, item in fakes:
        if sig_loai in indexed_groups and item in indexed_groups[sig_loai]:
            indexed_groups[sig_loai].remove(item)

        original_no_idx_sig = item.get('_evicted_from')
        if original_no_idx_sig and original_no_idx_sig in no_index_groups:
            no_index_groups[original_no_idx_sig].append(item)
        else:
            margin, avg_size = item.get('x0', 0), round(item.get('avg_size', 0), 1)
            font_name = item.get('fontname', 'UNKNOWN')
            no_idx_sig = f"NO_INDEX_Margin({round(margin, 1)})_Size({avg_size})_Font({font_name})"
            no_index_groups[no_idx_sig].append(item)

        if 'extracted_index' in item:
            del item['extracted_index']

    empty_keys = [k for k, v in indexed_groups.items() if not v]
    for k in empty_keys: del indexed_groups[k]

    return indexed_groups, no_index_groups

def analyze_and_print_parent_child(indexed_groups, no_index_groups, margin_tolerance=5):
    def get_rep(items):
        if not items: return None, None, None
        return (items[0].get('x0', 0), items[0].get('fontname', 'UNKNOWN'), round(items[0].get('avg_size', 0), 1))

    def print_block(sig, items):
        if not items: return
        margin, fontname, avg_size = get_rep(items)
        print(f"\n[ Nhóm: {sig} | Lề: {round(margin, 1)} | Font: {fontname} | Size: {avg_size} ]")
        for item in items:
            idx  = item.get('extracted_index', '')
            print(f"  + {idx:<10} | {item.get('text', '')}")

    # In thẳng từng nhóm đã được xử lý ở các bước trước, không gộp gì thêm
    for sig, items in indexed_groups.items():
        print_block(sig, items)

    for sig, items in no_index_groups.items():
        print_block(sig, items)

def process_toc_v2(real_heading_muc_luc):
    indexed_toc, no_index_toc = group_all_headings(real_heading_muc_luc)
    has_hierarchy = check_hierarchy(indexed_toc, no_index_toc, margin_tolerance=5)

    print("===== MỤC LỤC TỔNG HỢP (PHIÊN BẢN CHÍNH THỨC) =====")

    if not has_hierarchy:
        final_groups = group_by_font_and_size(indexed_toc, no_index_toc)
        analyze_and_print_parent_child(final_groups, {}, margin_tolerance=5)

        # grouped_heading chính là final_groups
        grouped_heading = final_groups.copy()

        return final_groups, {}, grouped_heading
    else:
        indexed_toc, no_index_toc = merge_fake_indexed_to_no_index(indexed_toc, no_index_toc, margin_tolerance=5)
        indexed_toc, no_index_toc = split_mixed_category_groups(indexed_toc, no_index_toc)
        indexed_toc, no_index_toc = execute_reverse_hierarchy_check(indexed_toc, no_index_toc)

        analyze_and_print_parent_child(indexed_toc, no_index_toc, margin_tolerance=5)

        # TẠO BIẾN grouped_heading: Gộp chung cả 2 rổ lại thành 1 dictionary duy nhất
        grouped_heading = {}
        grouped_heading.update(indexed_toc)
        grouped_heading.update(no_index_toc)

        return indexed_toc, no_index_toc, grouped_heading

import re

from difflib import SequenceMatcher

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_start_idx_after_toc(struct_merged, real_heading_muc_luc):
    """
    Tìm chữ 'Mục lục' -> Lấy dòng liền sau -> Đối chiếu xuống real_heading (độ giống >= 80%).
    """
    # 1. Tìm vị trí dòng chỉ có từ mục lục / table of content / contents
    toc_idx = -1
    for i, row in enumerate(struct_merged):
        txt = row.get('Text', row.get('text', '')).strip().lower()
        if txt in ['mục lục', 'mucluc', 'table of content', 'table of contents', 'contents']:
            toc_idx = i
            break

    # 2. Lấy text dòng ngay phía sau dòng "mục lục"
    if toc_idx != -1 and toc_idx + 1 < len(struct_merged):
        candidate_text = struct_merged[toc_idx + 1].get('Text', struct_merged[toc_idx + 1].get('text', '')).strip()

        # 3. Xét trong real_heading_muc_luc xem dòng nào tương đồng >= 80%
        for k, item in enumerate(real_heading_muc_luc):
            r_text = item.get('text', '').strip() if isinstance(item, dict) else item.strip()

            if similar(candidate_text, r_text) >= 0.8:
                return k # Lấy vị trí này làm mốc

    # Fallback: Nếu không tìm thấy, mặc định lấy từ đầu danh sách
    return 0

def assign_levels_and_build_tree(grouped_heading, real_heading_muc_luc, struct_merged):
    """
    Gán bậc cho từng nhóm và xuất ra list data + cấu trúc cây dạng Text.
    """
    # 1. Tìm cột mốc chia cắt
    start_idx = get_start_idx_after_toc(struct_merged, real_heading_muc_luc)

    all_groups = []

    # 2. Xét từng nhóm đã gom để tìm ra độ ưu tiên
    for sig, items in grouped_heading.items():
        if not items: continue

        # Chỉ xét những item nằm trong phần behind_muc_luc (original_order >= start_idx)
        items_behind_toc = [item for item in items if item.get('original_order', -1) >= start_idx]

        if items_behind_toc:
            # Nhóm có xuất hiện sau chữ Mục Lục -> Ưu tiên dựa vào vị trí sớm nhất
            first_order_behind = min(item.get('original_order') for item in items_behind_toc)
        else:
            # Nhóm KHÔNG CÓ mặt sau Mục Lục -> Đẩy xuống bét (gán vô cực)
            first_order_behind = float('inf')

        absolute_first_order = min(item.get('original_order', float('inf')) for item in items)

        all_groups.append({
            'signature': sig,
            'first_order_behind': first_order_behind,
            'absolute_first_order': absolute_first_order,
            'items': items
        })

    # 3. Sắp xếp các nhóm để phân bậc (càng nhỏ càng ưu tiên)
    all_groups.sort(key=lambda g: (g['first_order_behind'], g['absolute_first_order']))

    # 4. Gán số Bậc (Level)
    order_to_level = {}
    current_level = 1
    for group in all_groups:
        for item in group['items']:
            order_to_level[item.get('original_order')] = current_level
        current_level += 1

    # BIẾN OUTPUT 1: real_heading_muc_luc_level
    real_heading_muc_luc_level = []
    for i, original_item in enumerate(real_heading_muc_luc):
        item_copy = original_item.copy() if isinstance(original_item, dict) else {'text': original_item}
        item_copy['level'] = order_to_level.get(i, 1)

        if 'extracted_index' not in item_copy:
            idx, _ = get_index_and_group(item_copy.get('text', ''))
            item_copy['extracted_index'] = idx if idx else ''

        real_heading_muc_luc_level.append(item_copy)

    # BIẾN OUTPUT 2: heading_muc_luc_tree
    tree_lines = []
    for item in real_heading_muc_luc_level:
        level = item.get('level', 1)
        text = item.get('text', '')

        # Bậc 1 thụt 0, Bậc 2 thụt 4 khoảng trắng, Bậc 3 thụt 8...
        indent = "    " * (level - 1)
        tree_lines.append(f"{indent}- {text}")

    heading_muc_luc_tree = "\n".join(tree_lines)

    # Trả về các biến đầu ra
    return real_heading_muc_luc_level, heading_muc_luc_tree, start_idx

def print_final_output(real_heading_muc_luc_level, heading_muc_luc_tree, start_idx):
    print("\n" + "="*80)
    print(" DANH SÁCH HEADING NẰM SAU MỤC LỤC (BEHIND MỤC LỤC) ".center(80, '='))
    print("="*80)
    behind_list = real_heading_muc_luc_level[start_idx:]
    if not behind_list:
        print("(Không có heading nào sau Mục lục / Hoặc không tìm thấy chữ Mục lục)")
    else:
        for i, item in enumerate(behind_list):
            real_stt = i + start_idx + 1
            text = item.get('text', '')
            print(f"[STT {real_stt:02d}] {text}")

    print("\n" + "="*80)
    print(" BẢNG DỮ LIỆU ĐÃ GẮN BẬC (LEVEL) ".center(80, '='))
    print("="*80)
    print(f"{'STT':<5} | {'Bậc':<4} | {'Chỉ số':<8} | {'Nội dung'}")
    print("-" * 110)
    for i, item in enumerate(real_heading_muc_luc_level, 1):
        level = item.get('level', '?')
        idx = item.get('extracted_index', '')
        text = item.get('text', '')
        print(f"{i:<5} | {level:<4} | {idx:<8} | {text}")

    print("\n" + "="*80)
    print(" CẤU TRÚC CÂY MỤC LỤC ".center(80, '='))
    print("="*80)
    print(heading_muc_luc_tree)

import difflib

def align_bookmark_with_toc(bookmark_tree, toc_items_list):
    """Đối chiếu Bookmark với TOC bằng thuật toán cửa sổ trượt (Sliding Window)"""
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

    return real_heading_muc_luc_level, heading_muc_luc_tree
