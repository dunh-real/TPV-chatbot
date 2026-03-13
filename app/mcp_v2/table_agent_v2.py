"""
Table Agent v2 - Dùng Gemini API
Chọn tables liên quan từ workspace
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp"))

from schema_service import schema_service
from gemini_service import gemini_service

logger = logging.getLogger(__name__)


class TableAgentV2:
    def _build_prompt(self, question: str, workspace_name: str) -> str:
        tables = schema_service.get_tables_by_workspace(workspace_name)
        workspace = schema_service.get_workspace(workspace_name)

        table_list = "\n".join(
            f'- "{t}": {schema_service.get_table_description(t)}'
            for t in tables
        )

        return f"""Bạn là Table Selector cho hệ thống Text-to-SQL (MSSQL).

Workspace: {workspace_name} - {workspace.get("description", "")}

Tables có sẵn:
{table_list}

Câu hỏi: "{question}"

Chọn tables CẦN THIẾT để trả lời. Trả về JSON:
{{
    "tables": ["<table1>", "<table2>"],
    "reason": "<lý do ngắn>"
}}"""

    def select_tables(self, question: str, workspace_name: str) -> dict:
        available_tables = schema_service.get_tables_by_workspace(workspace_name)
        if not available_tables:
            return {"tables": [], "reason": f"Workspace '{workspace_name}' không tồn tại"}

        try:
            result = gemini_service.generate(self._build_prompt(question, workspace_name), json_mode=True)
            selected = result.get("tables", [])

            valid_tables = [t for t in selected if t in available_tables]
            invalid = [t for t in selected if t not in available_tables]
            if invalid:
                logger.warning(f"[TableV2] tables không hợp lệ: {invalid}")

            logger.info(f"[TableV2] Selected: {valid_tables} | workspace={workspace_name}")
            return {"tables": valid_tables, "reason": result.get("reason", "")}

        except Exception as e:
            logger.error(f"[TableV2] error: {e}")
            return {"tables": [], "reason": str(e)}


table_agent_v2 = TableAgentV2()
