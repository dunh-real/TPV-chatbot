"""
Chat Endpoint - Stateless REST API
Client gửi: question, tenant_id, role_id, user_id
"""

import logging
import traceback

from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse, ErrorResponse

logger = logging.getLogger("uvicorn.error")

router = APIRouter()


@router.post(
    "/ask",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def ask_question(request: ChatRequest):
    """
    Gửi câu hỏi và nhận câu trả lời từ hệ thống RAG.
    """
    logger.info(f"[ASK] Received: question='{request.question}', tenant={request.tenant_id}, role={request.role_id}, user={request.user_id}, dept={request.department_id}")
    try:
        from app.core.chat import ChatSession

        chat_session = ChatSession()
        logger.info("[ASK] ChatSession created, calling chat_session()...")
        result, processing_time = chat_session.chat_session(
            query_input=request.question,
            tenant_id=request.tenant_id,
            access_role=request.role_id,
            employee_id=request.user_id,
            department_id=request.department_id,
        )

        logger.info(f"[ASK] Done in {processing_time:.2f}s, answer length={len(result.get('answer', ''))}")

        return ChatResponse(
            question=request.question,
            answer=result.get("answer", ""),
            sources=[],
            conversation_id=f"{request.tenant_id}:{request.user_id}",
            metadata={
                "processing_time_seconds": round(processing_time, 2),
                "citation": result.get("citation", ""),
                "tenant_id": request.tenant_id,
                "user_id": request.user_id,
                "role_id": request.role_id,
            },
        )

    except Exception as e:
        logger.error(f"[ASK] ERROR: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý câu hỏi: {type(e).__name__}: {e}")
