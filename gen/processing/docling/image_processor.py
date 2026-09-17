"""Được tách cơ học từ docling.ipynb; không thay đổi logic thuật toán."""

import fitz
import os

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
