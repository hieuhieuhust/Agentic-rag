import httpx
import streamlit as st

from frontend.api_client import ApiClient


def render_documents(client: ApiClient) -> str | None:
    st.sidebar.header("Tài liệu")
    uploaded = st.sidebar.file_uploader("Tải PDF", type=["pdf"])
    if st.sidebar.button("Bắt đầu xử lý") and uploaded:
        try:
            client.upload_document(
                uploaded.name,
                uploaded.type or "application/pdf",
                uploaded.getvalue(),
            )
            st.sidebar.success("Đã đưa tài liệu vào hàng đợi")
            st.rerun()
        except httpx.HTTPError as exc:
            st.sidebar.error(f"Upload thất bại: {exc}")

    try:
        documents = client.documents()
    except httpx.HTTPError:
        st.sidebar.error("Không lấy được danh sách tài liệu")
        return None

    options = {document["id"]: document["file_name"] for document in documents}
    if not options:
        st.sidebar.info("Chưa có tài liệu")
        return None
    return st.sidebar.selectbox(
        "Tài liệu đang dùng",
        options=list(options),
        format_func=lambda document_id: options[document_id],
    )
