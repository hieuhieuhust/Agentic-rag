import streamlit as st

from frontend.api_client import ApiClient
from frontend.auth_ui import render_auth
from frontend.chat_ui import render_chat
from frontend.document_ui import render_documents


st.set_page_config(page_title="Multimodal PDF RAG", layout="wide")
st.title("Multimodal PDF RAG")

token = render_auth()
if token:
    if st.sidebar.button("Đăng xuất"):
        st.session_state.clear()
        st.rerun()
    api = ApiClient(token)
    selected_document = render_documents(api)
    render_chat(api, selected_document)
