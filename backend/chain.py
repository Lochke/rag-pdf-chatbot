"""
chain.py - Xử lý logic LangChain: load PDF, tạo vector store (Chroma),
và xây dựng RAG chain có nhớ lịch sử chat (memory) theo từng session.

Mỗi session_id (vd: mỗi user/mỗi tab) có:
- vectorstore riêng (từ PDF họ upload)
- memory riêng (lịch sử chat riêng)
"""

import os
import shutil
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import ConversationalRetrievalChain

# Thư mục lưu vector store tạm theo từng session
CHROMA_BASE_DIR = Path("./chroma_data")
CHROMA_BASE_DIR.mkdir(exist_ok=True)

# Lưu state của từng session trong RAM
# (đơn giản cho đồ án; production thật sẽ dùng Redis/DB)
SESSION_STORE: dict[str, dict] = {}


def get_llm() -> ChatGoogleGenerativeAI:
    """Tạo LLM instance dùng Google Gemini."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.3,
        api_key=os.environ.get("GOOGLE_API_KEY"),
    )


def process_pdf_and_create_chain(session_id: str, pdf_path: str) -> int:
    """
    Đọc PDF, chia đoạn, tạo embedding + vector store, rồi build
    ConversationalRetrievalChain cho session này.

    Trả về số lượng đoạn (chunks) đã tạo, để báo cho người dùng.
    """
    # 1. Load PDF
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    if not documents:
        raise ValueError("Không đọc được nội dung từ file PDF này.")

    # 2. Chia đoạn nhỏ để embedding chính xác hơn
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
    )
    chunks = splitter.split_documents(documents)

    # 3. Tạo embedding + lưu vào Chroma (mỗi session 1 thư mục riêng)
    session_dir = CHROMA_BASE_DIR / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir)  # xoá vector store cũ nếu upload PDF mới

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.environ.get("GOOGLE_API_KEY"),
    )
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(session_dir),
    )

    # 4. Memory: chỉ nhớ 5 lượt chat gần nhất để tiết kiệm token
    memory = ConversationBufferWindowMemory(
        k=5,
        memory_key="chat_history",
        return_messages=True,
        output_key="answer",
    )

    # 5. Build chain: kết hợp retriever (tìm đoạn liên quan) + LLM + memory
    chain = ConversationalRetrievalChain.from_llm(
        llm=get_llm(),
        retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
        memory=memory,
        return_source_documents=True,
    )

    # Lưu lại để dùng cho các câu hỏi tiếp theo của session này
    SESSION_STORE[session_id] = {
        "chain": chain,
        "vectorstore": vectorstore,
        "pdf_name": Path(pdf_path).name,
    }

    return len(chunks)


def ask_question(session_id: str, question: str) -> dict:
    """
    Gửi câu hỏi vào chain của session đã có PDF.
    Trả về câu trả lời + tên các trang/đoạn nguồn đã dùng để trả lời.
    """
    session = SESSION_STORE.get(session_id)
    if session is None:
        raise ValueError(
            "Session này chưa upload PDF nào. Vui lòng upload PDF trước khi hỏi."
        )

    chain = session["chain"]
    result = chain.invoke({"question": question})

    # Lấy thông tin trang nguồn (để show "trích từ trang X" cho người dùng)
    sources = []
    for doc in result.get("source_documents", []):
        page = doc.metadata.get("page", "?")
        sources.append(f"Trang {page + 1 if isinstance(page, int) else page}")

    return {
        "answer": result["answer"],
        "sources": list(dict.fromkeys(sources)),  # bỏ trùng, giữ thứ tự
        "pdf_name": session["pdf_name"],
    }


def session_exists(session_id: str) -> bool:
    return session_id in SESSION_STORE


def clear_session(session_id: str) -> None:
    """Xoá session: vector store trên đĩa + state trong RAM."""
    session_dir = CHROMA_BASE_DIR / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir)
    SESSION_STORE.pop(session_id, None)

def get_chat_history(session_id: str) -> list[dict]:
    """Lấy lịch sử chat hiện tại (đang lưu trong memory) của 1 session."""
    session = SESSION_STORE.get(session_id)
    if session is None:
        raise ValueError("Session này chưa upload PDF nào.")

    chain = session["chain"]
    messages = chain.memory.chat_memory.messages  # list HumanMessage/AIMessage

    history = []
    for msg in messages:
        role = "user" if msg.type == "human" else "assistant"
        history.append({"role": role, "content": msg.content})

    return history