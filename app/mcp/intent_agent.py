"""
Intent Agent - Bước 1 trong pipeline Text-to-SQL
Nhiệm vụ: Phân loại câu hỏi → workspace phù hợp
"""

import json
import logging
import ollama
from schema_service import schema_service

logger = logging.getLogger(__name__)

MODEL_NAME = "qwen2.5:latest"


class IntentAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def _build_prompt(self, question: str) -> str:
        workspaces = schema_service.get_all_workspaces()
        workspace_list = "\n".join(
            f'- "{name}": {ws["description"]} | keywords: {", ".join(ws["keywords"])}'
            for name, ws in workspaces.items()
        )

        return f"""Bạn là Intent Classifier cho hệ thống Text-to-SQL.

Danh sách workspaces:
{workspace_list}

Câu hỏi: "{question}"

Nhiệm vụ: Chọn workspace phù hợp nhất với câu hỏi trên.

Trả về JSON hợp lệ, không giải thích thêm:
{{
    "workspace": "<tên workspace>",
    "confidence": <0.0 đến 1.0>,
    "reason": "<lý do ngắn gọn>"
}}

Nếu câu hỏi không liên quan đến bất kỳ workspace nào, trả về:
{{
    "workspace": "unknown",
    "confidence": 0.0,
    "reason": "<lý do>"
}}"""

    def classify(self, question: str) -> dict:
        """
        Phân loại câu hỏi vào workspace.
        Returns:
        {
            "workspace": "hr",
            "confidence": 0.95,
            "reason": "Câu hỏi về nhân viên"
        }
        """
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": self._build_prompt(question)}],
                format="json",
                options={"temperature": 0.0}
            )

            result = json.loads(response["message"]["content"])

            workspace = result.get("workspace", "unknown")
            confidence = float(result.get("confidence", 0.0))

            # Validate workspace tồn tại
            if workspace != "unknown" and not schema_service.get_workspace(workspace):
                logger.warning(f"LLM trả về workspace không hợp lệ: {workspace}")
                workspace = "unknown"
                confidence = 0.0

            logger.info(f"Intent: '{question[:50]}' → workspace={workspace} | confidence={confidence}")

            return {
                "workspace": workspace,
                "confidence": confidence,
                "reason": result.get("reason", "")
            }

        except Exception as e:
            logger.error(f"IntentAgent error: {e}")
            return {"workspace": "unknown", "confidence": 0.0, "reason": str(e)}


# Singleton
intent_agent = IntentAgent()
