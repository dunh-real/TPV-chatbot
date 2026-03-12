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
-- Ví dụ 1: Ai đã chấm công hôm nay? (QUẢN LÝ, department_ids = [1,2,3])
SELECT e.FullName, a.CheckInTime, a.CheckOutTime 
FROM Hrm_Attendancel a
JOIN Dms_Employee e ON a.EmployeeId = e.Id AND e.IsDeleted = 0
WHERE CAST(a.Date AS DATE) = CAST(GETDATE() AS DATE)
AND a.IsDeleted = 0 AND a.TenantId = 2
AND e.WorkDepartmentId IN (1,2,3)

-- Ví dụ 2: Tôi đã chấm công chưa? (employee_id = 11)
SELECT TOP 1 a.CheckInTime, a.CheckOutTime 
FROM Hrm_Attendancel a
WHERE a.EmployeeId = 11
AND CAST(a.Date AS DATE) = CAST(GETDATE() AS DATE)
AND a.IsDeleted = 0 AND a.TenantId = 2

-- Ví dụ 3: Nhân viên nào chưa chấm công hôm nay? (QUẢN LÝ, department_ids = [1,2,3])
SELECT e.Id, e.FullName FROM Dms_Employee e
WHERE e.IsDeleted = 0 AND e.TenantId = 2
AND e.WorkDepartmentId IN (1,2,3)
AND e.Id NOT IN (
    SELECT a.EmployeeId FROM Hrm_Attendancel a
    WHERE CAST(a.Date AS DATE) = CAST(GETDATE() AS DATE)
    AND a.IsDeleted = 0 AND a.TenantId = 2
)

-- Ví dụ 4: Có bao nhiêu đơn nghỉ phép đang chờ duyệt? (NHÂN VIÊN, employee_id = 5)
SELECT COUNT(*) AS total FROM Hrm_LeaveRequest
WHERE Status = 0 AND IsDeleted = 0 AND TenantId = 2
AND EmployeeId = 5
"""


class SQLAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def _build_prompt(self, question: str, schema_context: str, tenant_id: int = 0,
                       employee_id: int = 0, is_manager: bool = False, department_ids: list[int] = None) -> str:
        tenant_note = f"- Luôn thêm AND TenantId = {tenant_id} vào mọi table có cột TenantId" if tenant_id else ""
        
        # Build access control rules
        if is_manager and department_ids:
            dept_list = ",".join(str(d) for d in department_ids)
            access_note = f"""- PHÂN QUYỀN DỮ LIỆU: Người dùng hiện tại có employee_id = {employee_id}, là QUẢN LÝ, được xem dữ liệu của các phòng ban có WorkDepartmentId IN ({dept_list})
- Nếu câu hỏi hỏi về "tôi" hoặc "của tôi": dùng EmployeeId = {employee_id} (chỉ lấy data của chính người hỏi)
- Nếu câu hỏi hỏi về nhân viên/phòng ban/tổng hợp: dùng EmployeeId IN (SELECT Id FROM Dms_Employee WHERE WorkDepartmentId IN ({dept_list}) AND IsDeleted = 0 AND TenantId = {tenant_id})
- Với table Dms_Employee khi hỏi về "tôi": thêm AND Id = {employee_id}
- Với table Dms_Employee khi hỏi về phòng ban: thêm AND WorkDepartmentId IN ({dept_list})
- Với table Meeting_Meeting hoặc Meeting_AssginMeet có cột UserId khi hỏi về "tôi": thêm AND UserId = (SELECT UserId FROM Dms_Employee WHERE Id = {employee_id} AND IsDeleted = 0)
- Với table Meeting khi hỏi về phòng ban: thêm AND UserId IN (SELECT UserId FROM Dms_Employee WHERE WorkDepartmentId IN ({dept_list}) AND IsDeleted = 0 AND TenantId = {tenant_id})"""
        else:
            access_note = f"""- PHÂN QUYỀN DỮ LIỆU: Người dùng hiện tại có employee_id = {employee_id}, là NHÂN VIÊN, CHỈ được xem dữ liệu của chính mình
- Với các table có cột EmployeeId (như Hrm_Attendancel, Hrm_LeaveRequest): thêm AND EmployeeId = {employee_id}
- Với table Dms_Employee: thêm AND Id = {employee_id}
- Với table Meeting_Meeting hoặc Meeting_AssginMeet có cột UserId: thêm AND UserId = (SELECT UserId FROM Dms_Employee WHERE Id = {employee_id} AND IsDeleted = 0)"""

        return f"""Bạn là SQL Generator cho hệ thống MSSQL (SQL Server) multi-tenant.

{FEW_SHOT_EXAMPLES}

Schema cần dùng (CHỈ được dùng các columns liệt kê bên dưới, KHÔNG được tự thêm column khác):
{schema_context}

LƯU Ý QUAN TRỌNG:
- Chỉ dùng MSSQL syntax (không dùng MySQL hay PostgreSQL)
- Luôn thêm WHERE IsDeleted = 0 nếu table có cột IsDeleted (ABP soft delete)
{tenant_note}
- BẮT BUỘC: Khi query liên quan đến nhân viên, luôn JOIN Dms_Employee để lấy FullName thay vì chỉ trả về EmployeeId
- BẮT BUỘC PHÂN QUYỀN - KHÔNG ĐƯỢC BỎ QUA:
{access_note}
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

    def generate_and_execute(self, question: str, schema_context: str, tenant_id: int = 0,
                             employee_id: int = 0, is_manager: bool = False, department_ids: list[int] = None) -> dict:
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
        if department_ids is None:
            department_ids = []

        # Bước 1: Generate SQL
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": self._build_prompt(
                    question, schema_context, tenant_id=tenant_id,
                    employee_id=employee_id, is_manager=is_manager, department_ids=department_ids
                )}],
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
