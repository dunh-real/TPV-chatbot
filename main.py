"""
FastAPI Application Entry Point
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from app.core.config import settings
from app.api.endpoints import chat, upload, health

# Pre-load tất cả AI models (Reranker, Embedding, Qdrant, Redis) ngay khi start
# Để request đầu tiên không phải chờ load model
print("Đang khởi tạo AI services (Qdrant, Redis, Reranker, Embedding)...")
from app.core.chat import ChatSession  # noqa: E402
_chat_session = ChatSession()
print("Khởi tạo AI services hoàn tất.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown events"""
    # Startup: đảm bảo thư mục tồn tại
    settings.ensure_directories()
    print(f"🚀 TPV-Chatbot API đang chạy tại http://{settings.api_host}:{settings.api_port}")
    yield
    # Shutdown
    print("👋 Đang tắt server...")


app = FastAPI(
    title="TPV-Chatbot API",
    description="Hệ thống Hỏi Đáp Tài Liệu Nội Bộ sử dụng RAG",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware: đo thời gian xử lý request
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.time() - start:.4f}s"
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": str(exc),
        },
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        },
    )


# Register routers
api_prefix = f"/api/{settings.api_version}"
app.include_router(health.router, prefix=api_prefix, tags=["Health"])
app.include_router(upload.router, prefix=api_prefix, tags=["Upload"])
app.include_router(chat.router, prefix=api_prefix, tags=["Chat"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
