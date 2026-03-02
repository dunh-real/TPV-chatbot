"""
Chat Endpoint - Stateless REST API
Client gửi: question, tenant_id, role_id, user_id, department_id
Tự động route: RAG (tài liệu) hoặc MCP (database)
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
    Gửi câu hỏi và nhận câu trả lời.
    Tự động phân loại: hỏi về tài liệu → RAG, hỏi về dữ liệu → MCP Database.
    """
    try:
        from app.services.mcp_chat_service import intent_classifier, mcp_chat_service
        from app.services.memory_service import RedisChatMemory

        memory = RedisChatMemory()

        # 1. Phân loại intent
        intent = intent_classifier.classify(request.question)

        # 2. Route theo intent
        if intent == "db" and request.department_id:
            # Database query qua MCP
            chat_history = memory.get_history(request.tenant_id, request.user_id, limit=6)

            result = await mcp_chat_service.query_database(
                question=request.question,
                tenant_id=request.tenant_id,
                department_id=request.department_id,
                user_id=request.user_id,
                chat_history=chat_history,
            )

            # Lưu vào memory
            memory.add_message(request.tenant_id, request.user_id, "user", request.question)
            memory.add_message(request.tenant_id, request.user_id, "assistant", result["answer"])

            return ChatResponse(
                question=request.question,
                answer=result["answer"],
                sources=[],
                conversation_id=f"{request.tenant_id}:{request.user_id}",
                metadata={
                    "source_type": "database",
                    "tool_used": result.get("tool_used", ""),
                    "tenant_id": request.tenant_id,
                    "user_id": request.user_id,
                    "department_id": request.department_id,
                },
            )
        else:
            # RAG flow (giữ nguyên logic cũ)
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
                    "source_type": "rag",
                    "processing_time_seconds": round(processing_time, 2),
                    "citation": result.get("citation", ""),
                    "tenant_id": request.tenant_id,
                    "user_id": request.user_id,
                    "role_id": request.role_id,
                },
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý câu hỏi: {e}")
