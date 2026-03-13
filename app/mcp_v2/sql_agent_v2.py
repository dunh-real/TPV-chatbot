"""
SQL Agent v2 - Dùng Gemini API + Post-processor
LLM chỉ lo generate SQL logic, post-processor enforce security rules.
"""

import json
import re
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp"))

from mssql_service import mssql_service
from gemini_service import gemini_service
from sql_postprocessor import sql_postprocessor

logger = logging.getLogger(__name__)

FEW_SHOT_EXAMPLES = """
-- Ví dụ 1: Ai đã chấm công hôm nay?
SELECT e.FullName, a.CheckInTime, a.CheckOutTime
FROM Hrm_Attendancel a
JOIN Dms_Employee e ON a.EmployeeId = e.Id AND e.IsDeleted = 0
WHERE CAST(a.Date AS DATE) = CAST(GETDATE() AS DATE)
AND a.IsDeleted = 0 AND a.TenantId = 2

-- Ví dụ 2: Tôi đã chấm công chưa? (employee_id = 11)
SELECT TOP 1 a.CheckInTime, a.CheckOutTime
FROM Hrm_Attendancel a
WHERE a.EmployeeId = 11
AND CAST(a.Date AS DATE) = CAST(GETDATE() AS DATE)
AND a.IsDeleted = 0 AND a.TenantId = 2

-- Ví dụ 3: Nhân viên nào chưa chấm công hôm nay?
SELECT e.Id, e.FullName FROM Dms_Employee e
WHERE e.IsDeleted = 0 AND e.TenantId = 2
AND e.Id NOT IN (
    SELECT a.EmployeeId FROM Hrm_Attendancel a
    WHERE CAST(a.Date AS DATE) = CAST(GETDATE() AS DATE)
    AND a.IsDeleted = 0 AND a.TenantId = 2
)

-- Ví dụ 4: Đếm đơn nghỉ phép đang chờ duyệt
SELECT COUNT(*) AS total FROM Hrm_LeaveRequest
WHERE Status = 0 AND IsDeleted = 0 AND TenantId = 2

-- Ví dụ 5: Phòng ban có bao nhiêu nhân sự (dùng CTE recursive cho cây phòng ban)
WITH DeptTree AS (
    SELECT Id FROM Dms_WorkDepartment WHERE DisplayName LIKE N'%Công nghệ%' AND IsDeleted = 0 AND TenantId = 2
    UNION ALL
    SELECT d.Id FROM Dms_WorkDepartment d JOIN DeptTree dt ON d.ParentId = dt.Id WHERE d.IsDeleted = 0 AND d.TenantId = 2
)
SELECT COUNT(*) AS TotalStaff FROM Dms_Employee
WHERE WorkDepartmentId IN (SELECT Id FROM DeptTree) AND IsDeleted = 0 AND TenantId = 2
"""


class SQLAgentV2:
    def _build_prompt(self, question: str, schema_context: str, tenant_id: int = 0) -> str:
        """
        Prompt đơn giản - LLM chỉ lo business logic.
        Access filter sẽ do post-processor inject sau.
        """
        tenant_note = f"- Luôn thêm AND TenantId = {tenant_id} vào mọi table có cột TenantId" if tenant_id else ""

        return f"""Bạn là SQL Generator cho hệ thống MSSQL (SQL Server).

{FEW_SHOT_EXAMPLES}

Schema:
{schema_context}

RULES:
- Chỉ dùng MSSQL syntax
- Luôn thêm WHERE IsDeleted = 0 nếu table có cột IsDeleted
{tenant_note}
- Khi query liên quan đến nhân viên, luôn JOIN Dms_Employee để lấy FullName
- Khi so sánh chuỗi tiếng Việt (nvarchar), dùng N prefix: N'giá trị'
- Khi tìm theo tên, dùng LIKE thay vì = để linh hoạt: LIKE N'%keyword%'
- Dùng GETDATE() thay vì NOW(), TOP thay vì LIMIT
- KHÔNG dùng backtick hay ngoặc vuông
- Chỉ viết SELECT, không INSERT/UPDATE/DELETE
- KHÔNG dùng column nào không có trong Schema
- Dms_WorkDepartment có cấu trúc cây (ParentId). Khi hỏi về 1 phòng ban, dùng CTE recursive để lấy cả phòng con
- Luôn dùng alias ngắn: FROM Dms_Employee e

Câu hỏi: "{question}"

Trả về JSON:
{{
    "sql": "<câu SQL>",
    "explanation": "<giải thích ngắn>"
}}"""

    def _extract_valid_columns(self, schema_context: str) -> set[str]:
        cols = set()
        for line in schema_context.splitlines():
            if line.startswith("Columns:"):
                for match in re.finditer(r'(\w+)\s*\(', line):
                    cols.add(match.group(1))
        return cols

    def generate_and_execute(self, question: str, schema_context: str, tenant_id: int = 0,
                             employee_id: int = 0, is_manager: bool = False,
                             department_ids: list[int] = None) -> dict:
        if department_ids is None:
            department_ids = []

        # Step 1: LLM generate SQL (chỉ business logic)
        try:
            prompt = self._build_prompt(question, schema_context, tenant_id)
            result = gemini_service.generate(prompt, json_mode=True, temperature=0.0)

            sql = result.get("sql", "").strip()
            explanation = result.get("explanation", "")

            if not sql:
                return {"success": False, "sql": "", "data": [], "row_count": 0,
                        "explanation": "", "error": "LLM không generate được SQL"}

            if not sql.upper().startswith("SELECT") and not sql.upper().startswith("WITH"):
                sql = "SELECT " + sql

            logger.info(f"[SQLAgentV2] Raw SQL from Gemini: {sql[:150]}...")

        except Exception as e:
            logger.error(f"[SQLAgentV2] Gemini generate error: {e}")
            return {"success": False, "sql": "", "data": [], "row_count": 0,
                    "explanation": "", "error": str(e)}

        # Step 2: Post-process (enforce access filter, N prefix, etc.)
        try:
            sql = sql_postprocessor.process(
                sql, tenant_id=tenant_id, employee_id=employee_id,
                is_manager=is_manager, department_ids=department_ids
            )
        except Exception as e:
            logger.error(f"[SQLAgentV2] PostProcessor error: {e}")
            # Vẫn tiếp tục với SQL gốc nếu post-processor lỗi

        # Step 3: Execute
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
sql_agent_v2 = SQLAgentV2()
