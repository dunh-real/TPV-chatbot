"""
MCP Chat Service - Tích hợp MCP tools vào chat flow
Xử lý logic: phân loại câu hỏi → route tới RAG hoặc MCP → tổng hợp kết quả
"""

import json
import logging
import ollama
from typing import Optional
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from app.core.config import settings

logger = logging.getLogger(__name__)

NAME_LLM_MODEL = "qwen2.5:latest"


class IntentClassifier:
    """Phân loại câu hỏi: RAG (tài liệu) hay DB (dữ liệu database)"""

    CLASSIFY_PROMPT = """
    Bạn là bộ phân loại câu hỏi. Phân loại câu hỏi sau vào MỘT trong hai nhóm:

    - "rag": Câu hỏi về quy trình, chính sách, hướng dẫn, nội dung tài liệu, kiến thức chung
    - "db": Câu hỏi về dữ liệu cụ thể: danh sách nhân viên, số liệu thống kê, thông tin phòng ban, tìm kiếm người/tài liệu cụ thể trong hệ thống

    Chỉ trả về JSON: {"intent": "rag"} hoặc {"intent": "db"}

    Câu hỏi: {question}
    """

    @staticmethod
    def classify(question: str) -> str:
        """Trả về 'rag' hoặc 'db'"""
        try:
            response = ollama.chat(
                model=NAME_LLM_MODEL,
                messages=[{
                    "role": "user",
                    "content": IntentClassifier.CLASSIFY_PROMPT.format(question=question)
                }],
                format="json",
                options={"temperature": 0},
            )
            result = json.loads(response["message"]["content"])
            intent = result.get("intent", "rag")
            return intent if intent in ("rag", "db") else "rag"
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}, defaulting to 'rag'")
            return "rag"


class MCPChatService:
    """
    Gọi MCP tools thông qua LLM tool-calling.
    Flow: câu hỏi → LLM chọn tool → execute tool → LLM tổng hợp kết quả
    """

    def __init__(self):
        self.mcp_url = f"http://localhost:{settings.mcp_server_port}/mcp"

    async def query_database(
        self,
        question: str,
        tenant_id: str,
        department_id: int,
        user_id: str,
        chat_history: list = None,
    ) -> dict:
        """
        Xử lý câu hỏi liên quan đến database qua MCP.
        
        Flow:
        1. Lấy danh sách tools từ MCP Server
        2. Gửi câu hỏi + tools cho LLM để chọn tool phù hợp
        3. Execute tool qua MCP
        4. LLM tổng hợp kết quả thành câu trả lời
        """
        try:
            async with streamablehttp_client(self.mcp_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # 1. Lấy available tools
                    tools_result = await session.list_tools()
                    available_tools = self._format_tools_for_llm(tools_result.tools)

                    # 2. LLM chọn tool
                    tool_choice = self._llm_select_tool(
                        question, available_tools, department_id, tenant_id, chat_history
                    )

                    if not tool_choice:
                        return {
                            "answer": "Không tìm được công cụ phù hợp để trả lời câu hỏi này về dữ liệu.",
                            "source": "mcp",
                        }

                    # 3. Execute tool qua MCP (inject department_id + tenant_id)
                    tool_name = tool_choice["tool"]
                    tool_args = tool_choice.get("arguments", {})
                    tool_args["department_id"] = department_id
                    tool_args["tenant_id"] = tenant_id

                    result = await session.call_tool(tool_name, tool_args)
                    tool_output = result.content[0].text if result.content else "Không có dữ liệu"

                    # 4. LLM tổng hợp kết quả
                    final_answer = self._llm_synthesize(
                        question, tool_output, chat_history
                    )

                    return {
                        "answer": final_answer,
                        "source": "mcp",
                        "tool_used": tool_name,
                        "raw_data": tool_output,
                    }

        except Exception as e:
            logger.error(f"MCP query failed: {e}")
            return {
                "answer": f"Lỗi khi truy vấn dữ liệu: {str(e)}",
                "source": "mcp_error",
            }

    def _format_tools_for_llm(self, tools) -> str:
        """Format MCP tools thành mô tả cho LLM"""
        descriptions = []
        for tool in tools:
            desc = f"- {tool.name}: {tool.description}"
            if tool.inputSchema and "properties" in tool.inputSchema:
                params = []
                for k, v in tool.inputSchema["properties"].items():
                    if k not in ("department_id", "tenant_id"):  # Ẩn params tự inject
                        params.append(f"  + {k}: {v.get('description', v.get('type', ''))}")
                if params:
                    desc += "\n  Tham số:\n" + "\n".join(params)
            descriptions.append(desc)
        return "\n".join(descriptions)

    def _llm_select_tool(
        self, question: str, tools_desc: str,
        department_id: int, tenant_id: str,
        chat_history: list = None,
    ) -> Optional[dict]:
        """LLM chọn tool phù hợp dựa trên câu hỏi"""
        history_str = ""
        if chat_history:
            for msg in chat_history[-4:]:
                role = msg.get("role", "user")
                history_str += f"{role}: {msg['content']}\n"

        prompt = f"""
        Bạn là AI assistant có quyền truy cập database. Dựa trên câu hỏi, hãy chọn tool phù hợp nhất.

        TOOLS CÓ SẴN:
        {tools_desc}

        LỊCH SỬ:
        {history_str}

        CÂU HỎI: {question}

        CONTEXT: department_id={department_id}, tenant_id={tenant_id}
        (department_id và tenant_id sẽ được tự động thêm, KHÔNG cần truyền)

        Trả về JSON:
        {{"tool": "tên_tool", "arguments": {{...các tham số khác ngoài department_id và tenant_id...}}}}

        Nếu không có tool phù hợp, trả về: {{"tool": null}}
        """

        try:
            response = ollama.chat(
                model=NAME_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0},
            )
            result = json.loads(response["message"]["content"])
            if result.get("tool"):
                return result
            return None
        except Exception as e:
            logger.error(f"Tool selection failed: {e}")
            return None

    def _llm_synthesize(self, question: str, data: str, chat_history: list = None) -> str:
        """LLM tổng hợp dữ liệu thành câu trả lời tự nhiên"""
        history_str = ""
        if chat_history:
            for msg in chat_history[-4:]:
                history_str += f"{msg.get('role', 'user')}: {msg['content']}\n"

        prompt = f"""
        Dựa trên dữ liệu từ database, hãy trả lời câu hỏi bằng tiếng Việt, rõ ràng và chuyên nghiệp.

        LỊCH SỬ: {history_str}
        CÂU HỎI: {question}
        DỮ LIỆU TỪ DATABASE:
        {data}

        QUY TẮC:
        - Trả lời dựa trên dữ liệu được cung cấp, KHÔNG bịa thêm
        - Nếu dữ liệu trống hoặc lỗi, nói rõ "Không tìm thấy dữ liệu"
        - Format bảng biểu nếu phù hợp (dùng Markdown)
        - Trả về JSON: {{"answer": "câu trả lời", "citation": "database"}}
        """

        try:
            response = ollama.chat(
                model=NAME_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.2},
            )
            result = json.loads(response["message"]["content"])
            return result.get("answer", str(result))
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return f"Đã lấy được dữ liệu nhưng lỗi khi tổng hợp: {data[:500]}"


# Singleton instances
intent_classifier = IntentClassifier()
mcp_chat_service = MCPChatService()
