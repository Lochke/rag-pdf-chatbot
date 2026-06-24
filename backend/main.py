"""
main.py - FastAPI backend cho chatbot RAG.

Endpoints:
- POST /upload      : upload file PDF, tạo vector store cho session
- POST /chat        : gửi câu hỏi, nhận câu trả lời dựa trên PDF đã upload
- DELETE /session    : xoá session (PDF + lịch sử chat)
- GET  /health      : kiểm tra server còn sống (dùng cho healthcheck khi deploy)
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import chain as chain_module

load_dotenv()

app = FastAPI(title="Chatbot RAG API", version="1.0.0")

# Cho phép frontend (Streamlit, domain khác) gọi API này
# Khi deploy thật, nên giới hạn lại allow_origins thay vì "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE_MB = 20


class ChatRequest(BaseModel):
    session_id: str
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    pdf_name: str


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    chunks_created: int
    message: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Nhận file PDF, lưu tạm, xử lý thành vector store.
    Trả về session_id để client dùng cho các request /chat tiếp theo.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF.")

    # Kiểm tra dung lượng file (đọc tạm để check size)
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File quá lớn ({size_mb:.1f}MB). Giới hạn {MAX_FILE_SIZE_MB}MB.",
        )

    session_id = str(uuid.uuid4())

    # Lưu file tạm để PyPDFLoader đọc (loader cần đường dẫn file thật)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        chunks_created = chain_module.process_pdf_and_create_chain(
            session_id=session_id,
            pdf_path=tmp_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý PDF: {exc}")
    finally:
        os.unlink(tmp_path)  # luôn xoá file tạm dù thành công hay lỗi

    return UploadResponse(
        session_id=session_id,
        filename=file.filename,
        chunks_created=chunks_created,
        message="Upload và xử lý PDF thành công. Bạn có thể bắt đầu hỏi.",
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Gửi câu hỏi cho chatbot, dựa trên PDF đã upload của session này."""
    if not chain_module.session_exists(req.session_id):
        raise HTTPException(
            status_code=404,
            detail="Session không tồn tại hoặc chưa upload PDF. Vui lòng upload PDF trước.",
        )

    try:
        result = chain_module.ask_question(req.session_id, req.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý câu hỏi: {exc}")

    return ChatResponse(**result)

@app.get("/history/{session_id}")
def get_history(session_id: str):
    """Xem lại lịch sử chat (debug) đang lưu trong memory của session."""
    if not chain_module.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session không tồn tại.")

    try:
        history = chain_module.get_chat_history(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy lịch sử: {exc}")

    return {"session_id": session_id, "history": history}

@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    """Xoá session: dọn vector store + lịch sử chat."""
    chain_module.clear_session(session_id)
    return {"message": "Đã xoá session."}
