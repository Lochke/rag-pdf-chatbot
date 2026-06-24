# 🤖 Chatbot RAG - Hỏi đáp tài liệu PDF

Chatbot cho phép người dùng upload file PDF và hỏi đáp trực tiếp về nội dung tài liệu, sử dụng kỹ thuật **RAG (Retrieval Augmented Generation)** kết hợp với OpenAI GPT.

## Tính năng

- 📄 Upload PDF bất kỳ qua giao diện web
- 🔍 Tự động chia nhỏ, tạo embedding và lưu vào vector database (Chroma)
- 💬 Hỏi đáp dựa trên nội dung PDF, có trích dẫn số trang nguồn
- 🧠 Nhớ lịch sử hội thoại (memory) để hỏi tiếp theo có ngữ cảnh
- 🐳 Đóng gói Docker, kiến trúc tách biệt backend/frontend

## Kiến trúc

```
┌──────────────┐         HTTP API        ┌───────────────┐
│   Frontend   │ ───────────────────────> │    Backend    │
│  (Streamlit) │ <─────────────────────── │   (FastAPI)   │
└──────────────┘                          └───────┬───────┘
                                                   │
                                          ┌────────┴────────┐
                                          │   LangChain      │
                                          │ ┌─────────────┐  │
                                          │ │ Text Splitter│  │
                                          │ │ Embeddings   │  │
                                          │ │ Chroma (DB)  │  │
                                          │ │ Memory       │  │
                                          │ │ ConvRetrieval│  │
                                          │ │ Chain        │  │
                                          │ └─────────────┘  │
                                          └────────┬─────────┘
                                                   │
                                            OpenAI API (GPT)
```

## Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| LLM | Google Gemini (`gemini-3-flash`) |
| Framework AI | LangChain |
| Vector Database | Chroma |
| Embeddings | Google Generative AI Embeddings |
| Backend API | FastAPI |
| Frontend | Streamlit |
| Containerization | Docker, Docker Compose |

## Chạy local (development)

### Yêu cầu
- Python 3.12+
- Docker & Docker Compose (khuyến nghị)
- API key của Google Gemini (miễn phí — [lấy tại đây](https://aistudio.google.com/apikey))

### Cách 1: Dùng Docker Compose (khuyến nghị)

```bash
# 1. Clone repo
git clone <your-repo-url>
cd chatbot-rag

# 2. Tạo file .env từ mẫu, điền API key
cp .env.example .env
# Mở .env và điền GOOGLE_API_KEY=AIzaSy...

# 3. Build và chạy
docker compose up --build

# 4. Mở browser
# Frontend: http://localhost:8501
# Backend API docs: http://localhost:8000/docs
```

### Cách 2: Chạy thủ công không Docker

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
echo "GOOGLE_API_KEY=your-key-here" > .env
uvicorn main:app --reload --port 8000
```

**Frontend** (terminal khác):
```bash
cd frontend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Cách sử dụng

1. Mở `http://localhost:8501`
2. Upload file PDF ở sidebar bên trái, bấm "Xử lý PDF"
3. Đợi vài chục giây để hệ thống tạo vector embedding
4. Nhập câu hỏi vào khung chat — chatbot sẽ trả lời dựa trên nội dung PDF, kèm trích dẫn số trang

## Deploy lên Render

1. Push code lên GitHub
2. Tạo 2 Web Service trên [Render](https://render.com): một cho `backend/`, một cho `frontend/`, mỗi service chọn Docker runtime và trỏ đúng thư mục (Root Directory)
5. Thêm biến môi trường `GOOGLE_API_KEY` cho service backend (lấy từ https://aistudio.google.com/apikey)
4. Thêm biến môi trường `BACKEND_URL` cho service frontend, trỏ tới URL public của backend (vd: `https://your-backend.onrender.com`)
5. Render tự build và deploy từ Dockerfile có sẵn

## Cấu trúc project

```
chatbot-rag/
├── backend/
│   ├── main.py              # FastAPI app, định nghĩa API endpoints
│   ├── chain.py              # Logic LangChain: xử lý PDF, RAG chain, memory
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app.py                # Streamlit UI
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Hạn chế hiện tại

- Vector store và lịch sử chat lưu trong RAM/đĩa local của session — restart server sẽ mất dữ liệu (phù hợp cho mục đích demo/học tập, chưa phù hợp production thật)
- Chỉ hỗ trợ 1 PDF cho mỗi session tại một thời điểm
- Chưa có xác thực người dùng (authentication)

## Định hướng phát triển tiếp

- [ ] Lưu vector store + chat history vào database thật (PostgreSQL/Redis) để không mất dữ liệu khi restart
- [ ] Hỗ trợ upload nhiều PDF cùng lúc, hỏi đáp trên toàn bộ tập tài liệu
- [ ] Thêm xác thực người dùng
- [ ] Viết unit test với pytest + CI/CD bằng GitHub Actions
