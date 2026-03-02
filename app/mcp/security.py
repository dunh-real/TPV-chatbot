"""
Security layer cho MCP Database Tools
- SQL validation (chặn write operations)
- Audit logging
- Department-level access control
"""

import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Các keyword SQL nguy hiểm - KHÔNG cho phép
BLOCKED_SQL_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "EXEC", "EXECUTE", "xp_", "sp_", "GRANT",
    "REVOKE", "DENY", "BACKUP", "RESTORE", "SHUTDOWN",
    "DBCC", "BULK", "OPENROWSET", "OPENQUERY", "OPENDATASOURCE",
]

# Các system tables không cho truy cập
BLOCKED_TABLES = [
    "sys.", "INFORMATION_SCHEMA.", "master.", "msdb.", "tempdb.",
    "AbpUsers", "AbpRoles", "AbpPermissions", "AbpUserLogins",
    "AbpSettings", "AbpAuditLogs",
]


def validate_sql_safety(sql: str) -> tuple[bool, str]:
    """
    Validate SQL query an toàn trước khi execute.
    Returns: (is_safe, error_message)
    """
    sql_upper = sql.upper().strip()

    # Chỉ cho phép SELECT
    if not sql_upper.startswith("SELECT"):
        return False, "Chỉ cho phép câu lệnh SELECT"

    # Check blocked keywords
    for keyword in BLOCKED_SQL_KEYWORDS:
        pattern = rf'\b{keyword}\b'
        if re.search(pattern, sql_upper):
            return False, f"Từ khóa '{keyword}' không được phép sử dụng"

    # Check blocked tables
    for table in BLOCKED_TABLES:
        if table.upper() in sql_upper:
            return False, f"Không được phép truy cập '{table}'"

    # Check for comments (có thể dùng để bypass)
    if "--" in sql or "/*" in sql:
        return False, "Không được phép sử dụng SQL comments"

    # Check for multiple statements (;)
    # Loại bỏ string literals trước khi check
    sql_no_strings = re.sub(r"'[^']*'", "", sql)
    if ";" in sql_no_strings:
        return False, "Không được phép thực thi nhiều câu lệnh"

    return True, ""


def audit_log(
    user_id: str,
    tenant_id: str,
    department_id: int,
    tool_name: str,
    parameters: dict,
    success: bool,
    error: str = ""
):
    """Ghi log audit cho mọi truy vấn DB qua MCP"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "tenant_id": tenant_id,
        "department_id": department_id,
        "tool": tool_name,
        "parameters": parameters,
        "success": success,
        "error": error,
    }

    if success:
        logger.info(f"MCP_AUDIT: {log_entry}")
    else:
        logger.warning(f"MCP_AUDIT_DENIED: {log_entry}")
