"""
MSSQL Service - Kết nối database với readonly user
- Connection pooling để tái sử dụng kết nối
- Chỉ cho phép SELECT (readonly user + validator)
- Tự động thêm TOP nếu thiếu để tránh full scan
- Timeout bảo vệ tránh query chạy quá lâu
"""

import os
import re
import logging
import pyodbc
from typing import Any
from dotenv import load_dotenv

from pathlib import Path
load_dotenv(Path(__file__).parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

# ==================== Config ====================
MSSQL_SERVER   = os.getenv("MSSQL_SERVER", "100.122.181.72")
MSSQL_DATABASE = os.getenv("MSSQL_DATABASE", "erps")
MSSQL_USER     = os.getenv("MSSQL_USER", "ai_readonly_user")
MSSQL_PASSWORD = os.getenv("MSSQL_PASSWORD", "")
MSSQL_TIMEOUT  = int(os.getenv("MSSQL_TIMEOUT", "10"))
MAX_ROWS       = int(os.getenv("MSSQL_MAX_ROWS", "100"))

# Các từ khóa bị chặn tuyệt đối (dùng word boundary để tránh false positive)
BLOCKED_KEYWORDS = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b", r"\bTRUNCATE\b",
    r"\bALTER\b", r"\bCREATE\b", r"\bEXEC\b", r"\bEXECUTE\b", r"\bGRANT\b",
    r"\bREVOKE\b", r"\bMERGE\b", r"\bBULK\b", r"\bOPENROWSET\b", r"\bOPENDATASOURCE\b"
]


class MSSQLService:
    def __init__(self):
        self._connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={MSSQL_SERVER};"
            f"DATABASE={MSSQL_DATABASE};"
            f"UID={MSSQL_USER};"
            f"PWD={MSSQL_PASSWORD};"
            f"Connection Timeout={MSSQL_TIMEOUT};"
        )
        self._conn: pyodbc.Connection | None = None

    # ==================== Connection ====================

    def _get_connection(self) -> pyodbc.Connection:
        """Lấy connection, tạo mới nếu chưa có hoặc đã đóng."""
        try:
            if self._conn is None:
                self._conn = pyodbc.connect(self._connection_string, timeout=MSSQL_TIMEOUT)
                self._conn.timeout = MSSQL_TIMEOUT
                logger.info(f"Connected to MSSQL: {MSSQL_SERVER}/{MSSQL_DATABASE}")
            else:
                # Ping để kiểm tra connection còn sống không
                self._conn.execute("SELECT 1")
        except Exception:
            # Reconnect nếu connection chết
            logger.warning("Connection lost, reconnecting...")
            self._conn = pyodbc.connect(self._connection_string, timeout=MSSQL_TIMEOUT)
            self._conn.timeout = MSSQL_TIMEOUT

        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("MSSQL connection closed")

    # ==================== Validator ====================

    def _validate_sql(self, sql: str) -> tuple[bool, str]:
        """
        Kiểm tra SQL có an toàn không.
        Returns: (is_safe, error_message)
        """
        sql_upper = sql.upper().strip()

        # Phải bắt đầu bằng SELECT hoặc WITH (CTE)
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            return False, "Chỉ cho phép câu lệnh SELECT hoặc WITH (CTE)"

        # Chặn các từ khóa nguy hiểm (word boundary)
        for pattern in BLOCKED_KEYWORDS:
            if re.search(pattern, sql_upper):
                keyword = pattern.replace(r"\b", "")
                return False, f"Từ khóa không được phép: {keyword}"

        # Chặn comment (có thể dùng để bypass)
        if "--" in sql or "/*" in sql:
            return False, "Không cho phép comment trong SQL"

        return True, ""

    def _inject_top(self, sql: str) -> str:
        """Tự động thêm TOP nếu SELECT chưa có, tránh full table scan."""
        sql_upper = sql.upper().strip()
        if "TOP " not in sql_upper and "FETCH NEXT" not in sql_upper:
            sql = sql.strip().replace("SELECT ", f"SELECT TOP {MAX_ROWS} ", 1)
        return sql

    # ==================== Execute ====================

    def execute(self, sql: str) -> dict[str, Any]:
        """
        Thực thi SQL và trả về kết quả.
        Returns:
            {
                "success": bool,
                "data": list[dict],   # Kết quả query
                "row_count": int,
                "error": str          # Nếu có lỗi
            }
        """
        # 1. Validate
        is_safe, error_msg = self._validate_sql(sql)
        if not is_safe:
            logger.warning(f"Blocked SQL: {error_msg} | SQL: {sql[:100]}")
            return {"success": False, "data": [], "row_count": 0, "error": error_msg}

        # 2. Inject TOP nếu cần
        sql = self._inject_top(sql)

        # 3. Execute
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)

            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            data = [dict(zip(columns, row)) for row in rows]

            logger.info(f"Query OK | rows={len(data)} | sql={sql[:80]}...")
            return {"success": True, "data": data, "row_count": len(data), "error": ""}

        except pyodbc.Error as e:
            error = str(e)
            logger.error(f"Query failed: {error} | sql={sql[:100]}")
            return {"success": False, "data": [], "row_count": 0, "error": error}

    # ==================== Schema helpers ====================

    def get_table_columns(self, table_name: str) -> dict[str, Any]:
        """Lấy danh sách columns của 1 table."""
        sql = f"""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
        """
        result = self.execute(sql)
        return result

    def get_all_tables(self) -> dict[str, Any]:
        """Lấy danh sách tất cả tables trong database."""
        sql = """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """
        return self.execute(sql)

    def test_connection(self) -> bool:
        """Kiểm tra kết nối có hoạt động không."""
        try:
            result = self.execute("SELECT 1 AS test")
            return result["success"]
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


# Singleton
mssql_service = MSSQLService()
