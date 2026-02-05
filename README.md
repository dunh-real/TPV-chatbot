# AI Chatbot RAG - Hệ thống Hỏi Đáp Tài Liệu Nội Bộ

## 📋 Tổng Quan

Hệ thống chatbot sử dụng RAG (Retrieval-Augmented Generation) để trả lời câu hỏi dựa trên tài liệu nội bộ công ty. Hệ thống sử dụng:

- **OCR**: LightOnOCR-1B để trích xuất text từ PDF
- **Chunking**: Small-to-Big Retrieval (2 tầng: Parent chunks theo Markdown Header, Child chunks theo Semantic)
- **Vector DB**: Qdrant để lưu trữ và tìm kiếm embeddings
- **Embedding**: all-MiniLM-L6-v2
- **LLM**: Ollama (llama3.1 hoặc tùy chọn)
- **Cache**: Redis để lưu conversation history

## 🏗️ Kiến Trúc Hệ Thống

```
User Upload PDF → OCR (LightOnOCR) → Markdown
                                       ↓
                            Chunking 2 tầng:
                            1. Parent (theo Header 2)
                            2. Child (semantic)
                                       ↓
                            Embedding → Qdrant
                                       
User Question → Embedding → Search Child Chunks (top-10)
                              ↓
                         Rerank (top-5)
                              ↓
                      Lấy Parent Chunks tương ứng
                              ↓
                    LLM (với context) → JSON Response
                              ↓
                       Redis (lưu history)
```

## 📁 Cấu Trúc Thư Mục

```
ai-chatbot-rag/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       ├── upload.py       # Endpoint upload PDF
│   │       ├── chat.py         # Endpoint chat/ask
│   │       └── health.py       # Health check
│   ├── core/
│   │   ├── config.py          # ✅ Configuration (HOÀN THÀNH)
│   │   └── constants.py
│   ├── services/
│   │   ├── ocr_service.py     # 🔄 Tiếp theo: OCR processing
│   │   ├── chunking_service.py # 🔄 Small-to-Big chunking
│   │   ├── vector_service.py  # 🔄 Qdrant operations
│   │   ├── llm_service.py     # 🔄 LLM interaction
│   │   └── rag_service.py     # 🔄 Orchestrator
│   ├── models/
│   │   └── schemas.py         # ✅ Pydantic models (HOÀN THÀNH)
│   └── utils/
│       └── logger.py          # ✅ Logging utility (HOÀN THÀNH)
├── data/
│   ├── raw/                   # PDF files
│   ├── markdown/              # Markdown từ OCR
│   └── vector_store/          # Qdrant storage
├── tests/
├── .env                       # ✅ Environment variables (HOÀN THÀNH)
├── .gitignore                 # ✅ Git ignore (HOÀN THÀNH)
├── Dockerfile                 # 🔄 Docker config
├── docker-compose.yml         # 🔄 Multi-service setup
├── main.py                    # 🔄 FastAPI app entry
└── requirements.txt           # ✅ Dependencies (HOÀN THÀNH)
```

## 🚀 Cài Đặt

### 1. Clone và Setup Environment

```bash
# Clone repository (hoặc tạo project mới)
git clone https://github.com/dunh-real/TPV-chatbot
cd ai-chatbot-rag

# Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc: venv\Scripts\activate  # Windows

# Cài đặt dependencies
pip install -r requirements.txt
```

### 2. Cấu Hình Environment Variables

Chỉnh sửa file `.env`:

```bash
# Qdrant
QDRANT_URL=http://localhost:6333

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# OCR Model path
OCR_MODEL_PATH=./models/LightOnOCR-1B

# LLM (Ollama)
LLM_BASE_URL=http://localhost:11434
LLM_MODEL_NAME=llama3.1
```

### 3. Khởi động Services

```bash
# Khởi động Qdrant (Docker)
docker run -p 6333:6333 -v $(pwd)/data/vector_store:/qdrant/storage qdrant/qdrant

# Khởi động Redis (Docker)
docker run -p 6379:6379 redis:7-alpine

# Khởi động Ollama (nếu chưa có)
# Tải về từ: https://ollama.ai
ollama pull llama3.1
```

### 4. Download Models

```bash
# Tải LightOnOCR-1B
# (Theo hướng dẫn của LightOnOCR)
mkdir -p models
# Download model vào models/LightOnOCR-1B/

# all-MiniLM-L6-v2 sẽ tự động download khi chạy lần đầu
```

## 💻 Sử dụng

### Chạy API Server

```bash
python main.py
# Hoặc: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### API Endpoints

#### 1. Upload PDF

```bash
curl -X POST "http://localhost:8000/api/v1/upload" \
  -F "file=@employee_handbook.pdf"
```

**Response:**
```json
{
  "success": true,
  "message": "File uploaded và xử lý thành công",
  "document_id": "doc_abc123",
  "filename": "employee_handbook.pdf",
  "total_parent_chunks": 45,
  "total_child_chunks": 234,
  "processing_time_seconds": 12.5
}
```

#### 2. Chat/Ask Question

```bash
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Chính sách nghỉ phép của công ty là gì?",
    "user_id": "user_123"
  }'
```

**Response:**
```json
{
  "question": "Chính sách nghỉ phép của công ty là gì?",
  "answer": "Theo tài liệu nội bộ, nhân viên chính thức được hưởng 12 ngày phép năm...",
  "sources": [
    {
      "chunk_id": "parent_chunk_123",
      "content": "## Chính sách nghỉ phép...",
      "source_file": "employee_handbook_2024.pdf",
      "page_number": 15,
      "relevance_score": 0.95
    }
  ],
  "conversation_id": "conv_xyz789",
  "metadata": {
    "processing_time_seconds": 2.3,
    "model_used": "llama3.1"
  }
}
```

#### 3. Health Check

```bash
curl "http://localhost:8000/api/v1/health"
```

## 🔧 Configuration

Tất cả cấu hình nằm trong file `.env`. Các tham số quan trọng:

| Tham số | Mô tả | Mặc định |
|---------|-------|----------|
| `CHILD_CHUNK_SIZE` | Kích thước child chunk | 512 |
| `TOP_K_CHILDREN` | Số children ban đầu | 10 |
| `TOP_K_RERANK` | Số chunks sau rerank | 5 |
| `LLM_TEMPERATURE` | Temperature của LLM | 0.1 |

## 🧪 Testing

```bash
# Chạy tests
pytest

# Với coverage
pytest --cov=app --cov-report=html
```

## 🐳 Docker

```bash
# Build image
docker build -t ai-chatbot-rag .

# Chạy với docker-compose (bao gồm Qdrant, Redis)
docker-compose up -d
```

## 📝 Roadmap

- [x] Setup cấu trúc project
- [x] Config và schemas
- [x] OCR Service
- [x] Chunking Service  
- [x] Vector Service
- [x] LLM Service
- [x] RAG Service (orchestrator)
- [ ] API Endpoints
- [ ] Testing
- [ ] Docker deployment

## 🤝 Contributing

1. Fork repository
2. Tạo branch mới (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Tạo Pull Request

## 📄 License

[MIT License](LICENSE)

## 👥 Team

TPV AI Engineering Team - Chatbot Project

---

**Note**: Đây là bản initial để format cấu trúc thư mục chuẩn chỉ cho các project về sau. Trong tương lai tôi sẽ (hoặc không) upload các file service (OCR, Chunking, Vector, LLM, RAG).