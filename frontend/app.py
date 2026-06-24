"""
app.py - Streamlit UI cho chatbot RAG.

Gọi sang backend FastAPI qua HTTP (BACKEND_URL), không gọi LangChain
trực tiếp ở đây — giữ frontend/backend tách biệt đúng kiến trúc production.
"""

import os

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Chatbot RAG - Hỏi đáp PDF", page_icon="🤖")
st.title("🤖 Chatbot hỏi đáp tài liệu PDF")
st.caption("Upload PDF, sau đó hỏi bất cứ điều gì về nội dung tài liệu.")

# --- State khởi tạo ---
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pdf_name" not in st.session_state:
    st.session_state.pdf_name = None


# --- Sidebar: upload PDF ---
with st.sidebar:
    st.header("📄 Upload tài liệu")
    uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])

    if uploaded_file is not None:
        if st.button("Xử lý PDF", type="primary", use_container_width=True):
            with st.spinner("Đang đọc và xử lý PDF... (có thể mất vài chục giây)"):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    resp = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=120)

                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state.session_id = data["session_id"]
                        st.session_state.pdf_name = data["filename"]
                        st.session_state.messages = []  # reset chat khi đổi PDF
                        st.success(
                            f"Đã xử lý xong! Tạo {data['chunks_created']} đoạn dữ liệu."
                        )
                    else:
                        st.error(f"Lỗi: {resp.json().get('detail', 'Không xác định')}")
                except requests.exceptions.ConnectionError:
                    st.error("Không kết nối được tới backend. Kiểm tra BACKEND_URL.")
                except requests.exceptions.Timeout:
                    st.error("Xử lý PDF quá lâu (timeout). Thử file nhỏ hơn.")

    if st.session_state.pdf_name:
        st.success(f"📌 Đang dùng: **{st.session_state.pdf_name}**")
        if st.button("📜 Xem lịch sử chat (backend)", use_container_width=True):
            try:
                resp = requests.get(f"{BACKEND_URL}/history/{st.session_state.session_id}")
                if resp.status_code == 200:
                    st.json(resp.json())
                else:
                    st.error(resp.json().get("detail", "Lỗi không xác định"))
            except requests.exceptions.ConnectionError:
                st.error("Không kết nối được tới backend.")
        if st.button("🗑️ Xoá session & PDF", use_container_width=True):
            if st.session_state.session_id:
                try:
                    requests.delete(f"{BACKEND_URL}/session/{st.session_state.session_id}")
                except requests.exceptions.ConnectionError:
                    pass
            st.session_state.session_id = None
            st.session_state.pdf_name = None
            st.session_state.messages = []
            st.rerun()

    st.divider()
    st.caption(f"Backend: `{BACKEND_URL}`")


# --- Khung chat chính ---
if not st.session_state.session_id:
    st.info("👈 Upload một file PDF ở sidebar để bắt đầu hỏi đáp.")
else:
    # Hiển thị lịch sử chat
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                st.caption(f"📎 Trích từ: {', '.join(msg['sources'])}")

    # Input câu hỏi mới
    question = st.chat_input("Nhập câu hỏi về nội dung PDF...")

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Đang suy nghĩ..."):
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/chat",
                        json={
                            "session_id": st.session_state.session_id,
                            "question": question,
                        },
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.markdown(data["answer"])
                        if data["sources"]:
                            st.caption(f"📎 Trích từ: {', '.join(data['sources'])}")
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": data["answer"],
                                "sources": data["sources"],
                            }
                        )
                    else:
                        error_msg = resp.json().get("detail", "Lỗi không xác định")
                        st.error(error_msg)
                except requests.exceptions.ConnectionError:
                    st.error("Không kết nối được tới backend.")
                except requests.exceptions.Timeout:
                    st.error("Câu trả lời quá lâu (timeout). Thử lại.")
