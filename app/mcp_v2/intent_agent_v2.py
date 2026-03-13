"""
Intent Agent v2 - Dùng Gemini API
Phân loại câu hỏi → workspace phù hợp
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp"))

from schema_service import schema_service
from gemini_service import gemini_service

logger = logging.getLogger(__name__)


class IntentAgentV2:
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

Chọn workspace phù hợp nhất. Trả về JSON:
{{
    "workspace": "<tên workspace>",
    "confidence": <0.0 đến 1.0>,
    "reason": "<lý do ngắn>"
}}

Nếu không liên quan workspace nào:
{{
    "workspace": "unknown",
    "confidence": 0.0,
    "reason": "<lý do>"
}}"""

    def classify(self, question: str) -> dict:
        try:
            result = gemini_service.generate(self._build_prompt(question), json_mode=True)

            workspace = result.get("workspace", "unknown")
            confidence = float(result.get("confidence", 0.0))

            if workspace != "unknown" and not schema_service.get_workspace(workspace):
                logger.warning(f"Gemini trả về workspace không hợp lệ: {workspace}")
                workspace = "unknown"
                confidence = 0.0

            logger.info(f"[IntentV2] '{question[:50]}' → workspace={workspace} | confidence={confidence}")
            return {"workspace": workspace, "confidence": confidence, "reason": result.get("reason", "")}

        except Exception as e:
            logger.error(f"[IntentV2] error: {e}")
            return {"workspace": "unknown", "confidence": 0.0, "reason": str(e)}


intent_agent_v2 = IntentAgentV2()
