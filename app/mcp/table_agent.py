"""
Table Agent - Bước 2 trong pipeline Text-to-SQL
Nhiệm vụ: Từ workspace → chọn đúng tables liên quan đến câu hỏi
"""

import json
import logging
import ollama
from schema_service import schema_service

logger = logging.getLogger(__name__)

MODEL_NAME = "qwen2.5:latest"


class TableAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def _build_prompt(self, question: str, workspace_name: str) -> str:
        tables = schema_service.get_tables_by_workspace(workspace_name)
        workspace = schema_service.get_workspace(workspace_name)

        table_list = "\n".join(
            f'- "{t}": {schema_service.get_table_description(t)}'
            for t in tables
        )

        return f"""Bạn là Table Selector cho hệ thống Text-to-SQL (MSSQL).

Workspace: {workspace_name} - {workspace.get("description", "")}

Danh sách tables có sẵn:
{table_list}

Câu hỏi: "{question}"

Nhiệm vụ: Chọn các tables CẦN THIẾT để trả lời câu hỏi trên.
- Chỉ chọn tables thực sự cần thiết, không chọn thừa
- Có thể chọn nhiều tables nếu cần JOIN

Trả về JSON hợp lệ, không giải thích thêm:
{{
    "tables": ["<table1>", "<table2>"],
    "reason": "<lý do ngắn gọn>"
}}"""

    def select_tables(self, question: str, workspace_name: str) -> dict:
        """
        Chọn tables phù hợp từ workspace.
        Returns:
        {
            "tables": ["Dms_Employee", "Hrm_Attendancel"],
            "reason": "Cần join Employee và Attendance"
        }
        """
        available_tables = schema_service.get_tables_by_workspace(workspace_name)
        if not available_tables:
            return {"tables": [], "reason": f"Workspace '{workspace_name}' không tồn tại"}

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": self._build_prompt(question, workspace_name)}],
                format="json",
                options={"temperature": 0.0}
            )

            result = json.loads(response["message"]["content"])
            selected = result.get("tables", [])

            # Validate: chỉ giữ tables thuộc workspace
            valid_tables = [t for t in selected if t in available_tables]
            invalid = [t for t in selected if t not in available_tables]
            if invalid:
                logger.warning(f"TableAgent trả về tables không hợp lệ: {invalid}")

            logger.info(f"Tables selected: {valid_tables} | workspace={workspace_name}")

            return {
                "tables": valid_tables,
                "reason": result.get("reason", "")
            }

        except Exception as e:
            logger.error(f"TableAgent error: {e}")
            return {"tables": [], "reason": str(e)}


# Singleton
table_agent = TableAgent()
