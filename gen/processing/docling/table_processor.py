"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""

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
