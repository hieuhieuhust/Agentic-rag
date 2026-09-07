import httpx
import streamlit as st

from frontend.api_client import ApiClient


def render_auth() -> str | None:
    # xác định xem đã đăng nhập hay chưa
    if st.session_state.get("access_token"):
        return st.session_state.access_token

    # chưa thì vẽ bước đăng nhập trong frontend
    login_tab, register_tab = st.tabs(["Đăng nhập", "Đăng ký"])
    with login_tab:
        username = st.text_input("Tên đăng nhập", key="login_username")
        password = st.text_input("Mật khẩu", type="password", key="login_password")
        if st.button("Đăng nhập", type="primary"):
            try:
                st.session_state.access_token = ApiClient().login(username, password)
                st.rerun()
            except httpx.HTTPError:
                st.error("Đăng nhập thất bại")

    with register_tab:
        username = st.text_input("Tên đăng nhập mới", key="register_username")
        password = st.text_input(
            "Mật khẩu mới", type="password", key="register_password"
        )
        if st.button("Tạo tài khoản"):
            try:
                ApiClient().register(username, password)
                st.success("Đăng ký thành công, hãy đăng nhập")
            except httpx.HTTPError:
                st.error("Không thể tạo tài khoản")
    return None
