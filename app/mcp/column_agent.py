"""
Column Agent - Bước 3 trong pipeline Text-to-SQL
Nhiệm vụ: Từ tables đã chọn → prune columns không cần thiết
Giúp SQL Agent chỉ thấy columns liên quan → SQL chính xác hơn
"""

import json
import logging
import ollama
from schema_service import schema_service

logger = logging.getLogger(__name__)

MODEL_NAME = "qwen2.5:latest"

# Columns ABP framework luôn có nhưng không cần thiết cho business query
SYSTEM_COLUMNS = {
    "TenantId", "CreationTime", "CreatorUserId",
    "LastModificationTime", "LastModifierUserId",
    "IsDeleted", "DeleterUserId", "DeletionTime",
    "TextSearch", "Log"
}


class ColumnAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def _build_prompt(self, question: str, tables_schema: str) -> str:
        return f"""Bạn là Column Pruner cho hệ thống Text-to-SQL (MSSQL).

Schema của các tables:
{tables_schema}

Câu hỏi: "{question}"

Nhiệm vụ: Chọn các columns CẦN THIẾT để trả lời câu hỏi.
- Luôn giữ lại primary key (Id) và foreign keys (xxxId) nếu cần JOIN
- Chỉ chọn columns thực sự liên quan đến câu hỏi
- Không chọn columns thừa

Trả về JSON hợp lệ, không giải thích thêm:
{{
    "selected_columns": {{
        "<TableName>": ["<col1>", "<col2>"]
    }},
    "reason": "<lý do ngắn gọn>"
}}"""

    def _pre_prune(self, tables: list[str]) -> dict[str, list[dict]]:
        """Loại bỏ system columns trước khi gửi cho LLM."""
        result = {}
        for table in tables:
            columns = schema_service.get_columns(table)
            result[table] = [c for c in columns if c["name"] not in SYSTEM_COLUMNS]
        return result

    def _build_schema_str(self, pruned: dict[str, list[dict]]) -> str:
        lines = []
        for table, columns in pruned.items():
            description = schema_service.get_table_description(table)
            col_str = ", ".join(f"{c['name']} ({c['type']})" for c in columns)
            lines.append(f"Table: {table} ({description})")
            lines.append(f"Columns: {col_str}")
            lines.append("")
        return "\n".join(lines)

    def prune_columns(self, question: str, tables: list[str]) -> dict:
        """
        Prune columns không cần thiết.
        Returns:
        {
            "selected_columns": {
                "Dms_Employee": ["Id", "FullName"],
                "Hrm_Attendancel": ["Id", "EmployeeId", "Date", "CheckInTime"]
            },
            "schema_context": "<schema string tối giản cho SQL Agent>"
        }
        """
        if not tables:
            return {"selected_columns": {}, "schema_context": ""}

        # Bước 1: Pre-prune system columns
        pruned = self._pre_prune(tables)
        schema_str = self._build_schema_str(pruned)

        # Bước 2: LLM prune thêm
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": self._build_prompt(question, schema_str)}],
                format="json",
                options={"temperature": 0.0}
            )

            result = json.loads(response["message"]["content"])
            selected = result.get("selected_columns", {})

            # Validate: chỉ giữ columns thực sự tồn tại trong table
            validated = {}
            for table, cols in selected.items():
                if table not in pruned:
                    continue
                available = {c["name"] for c in pruned[table]}
                valid_cols = [c for c in cols if c in available]
                if valid_cols:
                    validated[table] = valid_cols

            # Bước 3: Build schema context tối giản cho SQL Agent
            schema_context = self._build_final_schema(validated)

            logger.info(f"Columns pruned: {validated}")

            return {
                "selected_columns": validated,
                "schema_context": schema_context,
                "reason": result.get("reason", "")
            }

        except Exception as e:
            logger.error(f"ColumnAgent error: {e}")
            # Fallback: dùng toàn bộ columns sau pre-prune
            schema_context = self._build_schema_str(pruned)
            return {
                "selected_columns": {t: [c["name"] for c in cols] for t, cols in pruned.items()},
                "schema_context": schema_context,
                "reason": f"Fallback do lỗi: {e}"
            }

    def _build_final_schema(self, selected_columns: dict[str, list[str]]) -> str:
        """Build schema string tối giản từ selected columns."""
        lines = []
        for table, cols in selected_columns.items():
            description = schema_service.get_table_description(table)
            all_cols = schema_service.get_columns(table)
            col_map = {c["name"]: c["type"] for c in all_cols}
            col_str = ", ".join(f"{c} ({col_map.get(c, '')})" for c in cols)
            lines.append(f"Table: {table} ({description})")
            lines.append(f"Columns: {col_str}")
            lines.append("")
        return "\n".join(lines)


# Singleton
column_agent = ColumnAgent()
