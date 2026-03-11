"""
SQL Agent - Bước 4 trong pipeline Text-to-SQL
Nhiệm vụ: Từ schema tối giản → generate SQL (MSSQL syntax) → execute
"""

import json
import logging
import ollama
from mssql_service import mssql_service

logger = logging.getLogger(__name__)

MODEL_NAME = "qwen2.5:latest"

# Few-shot examples giúp LLM generate đúng MSSQL syntax
FEW_SHOT_EXAMPLES = """
-- Ví dụ 1: Lọc bản ghi chưa xóa (ABP soft delete)
-- Q: Danh sách nhân viên đang làm việc?
SELECT e.Id, e.FullName FROM Dms_Employee e
WHERE e.IsDeleted = 0

-- Ví dụ 2: JOIN 2 tables
-- Q: Nhân viên nào chưa chấm công hôm nay?
SELECT e.Id, e.FullName FROM Dms_Employee e
WHERE e.IsDeleted = 0
AND e.Id NOT IN (
    SELECT a.EmployeeId FROM Hrm_Attendancel a
    WHERE CAST(a.Date AS DATE) = CAST(GETDATE() AS DATE)
    AND a.IsDeleted = 0
)

-- Ví dụ 3: COUNT + filter
-- Q: Có bao nhiêu đơn nghỉ phép đang chờ duyệt?
SELECT COUNT(*) AS total FROM Hrm_LeaveRequest
WHERE Status = 0 AND IsDeleted = 0

-- Ví dụ 4: Lọc theo khoảng thời gian
-- Q: Cuộc họp tuần này?
SELECT m.Id, m.Title, m.StartTime, m.EndTime FROM Meeting_Meeting m
WHERE m.IsDeleted = 0
AND m.StartTime >= DATEADD(DAY, 1-DATEPART(WEEKDAY, GETDATE()), CAST(GETDATE() AS DATE))
AND m.StartTime < DATEADD(DAY, 8-DATEPART(WEEKDAY, GETDATE()), CAST(GETDATE() AS DATE))
"""


class SQLAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def _build_prompt(self, question: str, schema_context: str) -> str:
        return f"""Bạn là SQL Generator cho hệ thống MSSQL (SQL Server).

{FEW_SHOT_EXAMPLES}

Schema cần dùng (CHỈ được dùng các columns liệt kê bên dưới, KHÔNG được tự thêm column khác):
{schema_context}

LƯU Ý QUAN TRỌNG:
- Chỉ dùng MSSQL syntax (không dùng MySQL hay PostgreSQL)
- Luôn thêm WHERE IsDeleted = 0 nếu table có cột IsDeleted (ABP soft delete)
- Dùng GETDATE() thay vì NOW()
- Dùng TOP thay vì LIMIT
- KHÔNG dùng backtick (`) hay ngoặc vuông ([]) cho tên cột/table thông thường
- Chỉ dùng alias ngắn gọn: FROM Dms_Employee e, không phải FROM [Dms_Employee] e
- Chỉ viết câu SELECT, không INSERT/UPDATE/DELETE
- TUYỆT ĐỐI không dùng column nào không có trong Schema ở trên

Câu hỏi: "{question}"

Trả về JSON hợp lệ, không giải thích thêm:
{{
    "sql": "<câu SQL hoàn chỉnh>",
    "explanation": "<giải thích ngắn gọn>"
}}"""

    def _extract_valid_columns(self, schema_context: str) -> set[str]:
        """Parse schema_context lấy tất cả column names hợp lệ."""
        import re
        cols = set()
        for line in schema_context.splitlines():
            if line.startswith("Columns:"):
                # "Columns: Id (int), FullName (nvarchar), ..."
                for match in re.finditer(r'(\w+)\s*\(', line):
                    cols.add(match.group(1))
        return cols

    def generate_and_execute(self, question: str, schema_context: str) -> dict:
        """
        Generate SQL từ câu hỏi + schema → execute → trả kết quả.
        Returns:
        {{
            "success": bool,
            "sql": "SELECT ...",
            "data": [...],
            "row_count": int,
            "explanation": "...",
            "error": ""
        }}
        """
        # Bước 1: Generate SQL
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": self._build_prompt(question, schema_context)}],
                format="json",
                options={"temperature": 0.0}
            )

            result = json.loads(response["message"]["content"])
            sql = result.get("sql", "").strip()
            explanation = result.get("explanation", "")

            if not sql:
                return {"success": False, "sql": "", "data": [], "row_count": 0,
                        "explanation": "", "error": "LLM không generate được SQL"}

            # Fallback: nếu LLM quên SELECT
            if not sql.upper().startswith("SELECT"):
                sql = "SELECT " + sql

            # Clean: loại bỏ bracket sai kiểu [TableName] ColumnName → ColumnName
            import re
            sql = re.sub(r'\[[A-Za-z_]+\]\s+([A-Za-z_]+)', r'\1', sql)

            # Warn nếu LLM dùng column ngoài schema
            valid_cols = self._extract_valid_columns(schema_context)
            if valid_cols:
                used = set(re.findall(r'\b([A-Z][a-zA-Z]+)\b', sql))
                unknown = used - valid_cols - {"SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN",
                    "JOIN", "LEFT", "RIGHT", "INNER", "ON", "AS", "TOP", "COUNT", "CAST",
                    "GETDATE", "DATE", "DATEADD", "DATEPART", "DAY", "WEEKDAY", "NULL",
                    "IS", "LIKE", "BETWEEN", "ORDER", "BY", "GROUP", "HAVING", "DISTINCT"}
                if unknown:
                    logger.warning(f"SQL dùng columns không trong schema: {unknown}")

            logger.info(f"Generated SQL: {sql[:100]}...")

        except Exception as e:
            logger.error(f"SQLAgent generate error: {e}")
            return {"success": False, "sql": "", "data": [], "row_count": 0,
                    "explanation": "", "error": str(e)}

        # Bước 2: Execute
        exec_result = mssql_service.execute(sql)

        return {
            "success": exec_result["success"],
            "sql": sql,
            "data": exec_result["data"],
            "row_count": exec_result["row_count"],
            "explanation": explanation,
            "error": exec_result["error"]
        }


# Singleton
sql_agent = SQLAgent()
