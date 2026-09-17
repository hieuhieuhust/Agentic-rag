import time

import httpx
import streamlit as st

from frontend.api_client import ApiClient


def render_chat(client: ApiClient, document_id: str | None) -> None:
    if st.session_state.get("chat_document_id") != document_id:
        st.session_state.chat_document_id = document_id
        st.session_state.chat_session_id = None

    if not st.session_state.get("chat_session_id"):
        try:
            chat = client.create_session(document_id)
            st.session_state.chat_session_id = chat["id"]
        except httpx.HTTPError as exc:
            st.error(f"Không tạo được phiên chat: {exc}")
            return

    session_id = st.session_state.chat_session_id
    try:
        for message in client.messages(session_id):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    except httpx.HTTPError:
        st.warning("Không tải được lịch sử chat")

    query = st.chat_input("Nhập câu hỏi")
    if not query:
        return
    with st.chat_message("user"):
        st.markdown(query)
    try:
        request = client.send_message(
            session_id, query, use_rag=document_id is not None
        )
        with st.chat_message("assistant"):
            placeholder = st.empty()
            for _ in range(180):
                status = client.request_status(request["request_id"])
                if status["status"] == "done":
                    placeholder.markdown(status["final_answer"])
                    break
                if status["status"] == "error":
                    placeholder.error(status.get("error") or "RAG xử lý thất bại")
                    break
                placeholder.info(f"Đang xử lý: {status['current_stage']}")
                time.sleep(2)
            else:
                placeholder.warning("Yêu cầu vẫn đang được xử lý")
    except httpx.HTTPError as exc:
        st.error(f"Không gửi được câu hỏi: {exc}")
