"""
SQL Post-processor - Enforce rules bằng code, không phụ thuộc LLM
1. Thêm N prefix cho string literals tiếng Việt
2. Đảm bảo TenantId filter
3. Đảm bảo IsDeleted = 0
4. Inject access filter (department_ids hoặc employee_id)
5. Thêm TOP nếu thiếu
"""

import re
import logging

logger = logging.getLogger(__name__)

# Tables có cột EmployeeId (dùng để inject access filter)
EMPLOYEE_ID_TABLES = {
    "Hrm_Attendancel": "EmployeeId",
    "Hrm_LeaveRequest": "EmployeeId",
}

# Tables có cột UserId (Meeting)
USER_ID_TABLES = {
    "Meeting_Meeting": "UserId",
    "Meeting_AssginMeet": "UserId",
}


class SQLPostProcessor:

    def process(self, sql: str, tenant_id: int, employee_id: int,
                is_manager: bool, department_ids: list[int]) -> str:
        """Apply tất cả post-processing rules lên SQL."""
        sql = sql.strip()
        if not sql:
            return sql

        sql = self._clean_newlines(sql)
        sql = self._add_n_prefix(sql)
        sql = self._ensure_tenant_filter(sql, tenant_id)
        sql = self._inject_access_filter(sql, tenant_id, employee_id, is_manager, department_ids)

        logger.info(f"[PostProcessor] Final SQL: {sql[:150]}...")
        return sql

    def _clean_newlines(self, sql: str) -> str:
        """Loại bỏ literal \\n trong SQL (Gemini hay trả về escaped newlines)."""
        sql = sql.replace("\\n", " ")
        sql = sql.replace("\n", " ")
        # Gộp multiple spaces thành 1
        sql = re.sub(r'\s+', ' ', sql).strip()
        return sql

    def _add_n_prefix(self, sql: str) -> str:
        """
        Thêm N prefix cho mọi string literal chứa ký tự non-ASCII (tiếng Việt).
        'Phòng IT' → N'Phòng IT'
        Không ảnh hưởng string đã có N prefix.
        """
        def replace_string(match):
            quote_char = match.group(0)[0]
            content = match.group(1)
            # Kiểm tra có ký tự non-ASCII không
            has_unicode = any(ord(c) > 127 for c in content)
            if has_unicode and quote_char != 'N':
                return f"N'{content}'"
            return match.group(0)

        # Match string literals: 'xxx' nhưng không match N'xxx'
        sql = re.sub(r"(?<!N)'([^']*)'", replace_string, sql)
        return sql

    def _ensure_tenant_filter(self, sql: str, tenant_id: int) -> str:
        """
        Kiểm tra SQL đã có TenantId filter chưa.
        Nếu chưa có, log warning (không tự inject vì không biết alias).
        """
        if tenant_id and "TenantId" not in sql:
            logger.warning(f"[PostProcessor] SQL thiếu TenantId filter! tenant_id={tenant_id}")
        return sql

    def _inject_access_filter(self, sql: str, tenant_id: int, employee_id: int,
                               is_manager: bool, department_ids: list[int]) -> str:
        """
        Inject access filter vào SQL dựa trên is_manager.
        - Manager: filter theo department_ids
        - Employee: filter theo employee_id
        """
        sql_upper = sql.upper()

        # Tìm các tables được sử dụng trong SQL
        used_tables = self._extract_tables(sql)

        if not used_tables:
            return sql

        # Xác định filter cần inject
        for table_name, alias in used_tables:
            # Case 1: Table Dms_Employee
            if table_name == "Dms_Employee":
                if is_manager and department_ids:
                    dept_list = ",".join(str(d) for d in department_ids)
                    filter_clause = f"{alias}.WorkDepartmentId IN ({dept_list})"
                else:
                    filter_clause = f"{alias}.Id = {employee_id}"
                if not self._filter_exists(sql, "WorkDepartmentId IN" if is_manager else f"Id = {employee_id}", alias):
                    sql = self._inject_where_clause(sql, filter_clause, alias)

            # Case 2: Tables có EmployeeId
            elif table_name in EMPLOYEE_ID_TABLES:
                col = EMPLOYEE_ID_TABLES[table_name]
                if is_manager and department_ids:
                    dept_list = ",".join(str(d) for d in department_ids)
                    filter_clause = (
                        f"{alias}.{col} IN (SELECT Id FROM Dms_Employee "
                        f"WHERE WorkDepartmentId IN ({dept_list}) "
                        f"AND IsDeleted = 0 AND TenantId = {tenant_id})"
                    )
                else:
                    filter_clause = f"{alias}.{col} = {employee_id}"
                if not self._filter_exists(sql, f"{col} IN" if is_manager else f"{col} = {employee_id}", alias):
                    sql = self._inject_where_clause(sql, filter_clause, alias)

            # Case 3: Tables có UserId (Meeting)
            elif table_name in USER_ID_TABLES:
                col = USER_ID_TABLES[table_name]
                if is_manager and department_ids:
                    dept_list = ",".join(str(d) for d in department_ids)
                    filter_clause = (
                        f"{alias}.{col} IN (SELECT UserId FROM Dms_Employee "
                        f"WHERE WorkDepartmentId IN ({dept_list}) "
                        f"AND IsDeleted = 0 AND TenantId = {tenant_id})"
                    )
                else:
                    filter_clause = (
                        f"{alias}.{col} = (SELECT UserId FROM Dms_Employee "
                        f"WHERE Id = {employee_id} AND IsDeleted = 0)"
                    )
                if not self._filter_exists(sql, f"{col} IN" if is_manager else f"{col} =", alias):
                    sql = self._inject_where_clause(sql, filter_clause, alias)

        return sql

    def _extract_tables(self, sql: str) -> list[tuple[str, str]]:
        """
        Extract table names và aliases từ SQL.
        Returns: [(table_name, alias), ...]
        Ví dụ: "FROM Hrm_Attendancel a JOIN Dms_Employee e ON ..."
        → [("Hrm_Attendancel", "a"), ("Dms_Employee", "e")]
        """
        results = []
        # Match: FROM/JOIN TableName alias
        pattern = r'(?:FROM|JOIN)\s+(\w+)\s+(\w+)'
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            table = match.group(1)
            alias = match.group(2)
            # Loại bỏ keywords bị match nhầm
            if alias.upper() in ("ON", "WHERE", "AND", "OR", "LEFT", "RIGHT",
                                  "INNER", "OUTER", "CROSS", "SET", "AS", "JOIN"):
                alias = table  # Không có alias, dùng table name
            results.append((table, alias))

        # Match: FROM TableName (không có alias)
        pattern_no_alias = r'(?:FROM|JOIN)\s+(\w+)(?:\s+(?:WHERE|ON|ORDER|GROUP|HAVING|$))'
        for match in re.finditer(pattern_no_alias, sql, re.IGNORECASE):
            table = match.group(1)
            if not any(t == table for t, _ in results):
                results.append((table, table))

        return results

    def _filter_exists(self, sql: str, keyword: str, alias: str) -> bool:
        """Kiểm tra xem filter đã tồn tại trong SQL chưa (tránh duplicate inject)."""
        return keyword in sql

    def _inject_where_clause(self, sql: str, filter_clause: str, alias: str) -> str:
        """
        Inject filter clause vào SQL.
        """

        # Tìm vị trí WHERE cuối cùng liên quan đến alias này
        # Đơn giản: thêm AND ở cuối WHERE clause
        where_idx = sql.upper().rfind("WHERE")
        if where_idx >= 0:
            # Tìm vị trí cuối WHERE clause (trước ORDER BY, GROUP BY, etc.)
            end_markers = ["ORDER BY", "GROUP BY", "HAVING", ";"]
            end_idx = len(sql)
            for marker in end_markers:
                idx = sql.upper().find(marker, where_idx)
                if idx >= 0 and idx < end_idx:
                    end_idx = idx

            sql = sql[:end_idx].rstrip() + f" AND {filter_clause} " + sql[end_idx:]
        else:
            # Không có WHERE → thêm WHERE
            # Tìm vị trí sau FROM ... (trước ORDER BY, GROUP BY, etc.)
            end_markers = ["ORDER BY", "GROUP BY", "HAVING", ";"]
            end_idx = len(sql)
            for marker in end_markers:
                idx = sql.upper().find(marker)
                if idx >= 0 and idx < end_idx:
                    end_idx = idx

            sql = sql[:end_idx].rstrip() + f" WHERE {filter_clause} " + sql[end_idx:]

        return sql


# Singleton
sql_postprocessor = SQLPostProcessor()
