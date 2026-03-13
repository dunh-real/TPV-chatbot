"""
Column Agent v2 - Dùng Gemini API
Prune columns không liên quan
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp"))

from schema_service import schema_service
from gemini_service import gemini_service

logger = logging.getLogger(__name__)

SYSTEM_COLUMNS = {
    "TenantId", "CreationTime", "CreatorUserId",
    "LastModificationTime", "LastModifierUserId",
    "IsDeleted", "DeleterUserId", "DeletionTime",
    "TextSearch", "Log"
}


class ColumnAgentV2:
    def _build_prompt(self, question: str, tables_schema: str) -> str:
        return f"""Bạn là Column Pruner cho hệ thống Text-to-SQL (MSSQL).

Schema:
{tables_schema}

Câu hỏi: "{question}"

Chọn columns CẦN THIẾT. Luôn giữ Id và foreign keys (xxxId) nếu cần JOIN.
Trả về JSON:
{{
    "selected_columns": {{
        "<TableName>": ["<col1>", "<col2>"]
    }},
    "reason": "<lý do ngắn>"
}}"""

    def _pre_prune(self, tables: list[str]) -> dict[str, list[dict]]:
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
        if not tables:
            return {"selected_columns": {}, "schema_context": ""}

        pruned = self._pre_prune(tables)
        schema_str = self._build_schema_str(pruned)

        try:
            result = gemini_service.generate(self._build_prompt(question, schema_str), json_mode=True)
            selected = result.get("selected_columns", {})

            validated = {}
            for table, cols in selected.items():
                if table not in pruned:
                    continue
                available = {c["name"] for c in pruned[table]}
                valid_cols = [c for c in cols if c in available]
                if valid_cols:
                    validated[table] = valid_cols

            schema_context = self._build_final_schema(validated)
            logger.info(f"[ColumnV2] Pruned: {validated}")

            return {
                "selected_columns": validated,
                "schema_context": schema_context,
                "reason": result.get("reason", "")
            }

        except Exception as e:
            logger.error(f"[ColumnV2] error: {e}")
            schema_context = self._build_schema_str(pruned)
            return {
                "selected_columns": {t: [c["name"] for c in cols] for t, cols in pruned.items()},
                "schema_context": schema_context,
                "reason": f"Fallback: {e}"
            }

    def _build_final_schema(self, selected_columns: dict[str, list[str]]) -> str:
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


column_agent_v2 = ColumnAgentV2()
