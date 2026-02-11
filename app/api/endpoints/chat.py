"""
Chat Endpoint - Stateless REST API
Client gửi: question, tenant_id, role_id, user_id
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse, ErrorResponse

router = APIRouter()


@router.post(
    "/ask",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def ask_question(request: ChatRequest):
    """
    Gửi câu hỏi và nhận câu trả lời từ hệ thống RAG.

    Request body:
        - question: tin nhắn / câu hỏi
        - tenant_id: ID tenant (công ty/tổ chức)
        - role_id: role để phân quyền truy cập tài liệu
        - user_id: ID nhân viên (dùng cho conversation history)

    Flow: Query → Contextualize → Hybrid Search → Rerank → LLM → Response
    """
    try:
        from app.core.chat import ChatSession

        chat_session = ChatSession()
        result, processing_time = chat_session.chat_session(
            query_input=request.question,
            tenant_id=request.tenant_id,
            access_role=request.role_id,
            employee_id=request.user_id,
        )

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
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý câu hỏi: {e}")
