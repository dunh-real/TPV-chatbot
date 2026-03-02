"""
MSSQL Database Connection Pool
- Read-only connection cho AI queries
- Connection pooling để tối ưu performance
"""

import pyodbc
import logging
from contextlib import contextmanager
from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabasePool:
    """Quản lý connection pool tới MSSQL (read-only)"""

    def __init__(self):
        self._connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={settings.mssql_server};"
            f"DATABASE={settings.mssql_database};"
            f"UID={settings.mssql_user};"
            f"PWD={settings.mssql_password};"
            f"TrustServerCertificate=yes;"
            f"ApplicationIntent=ReadOnly;"
            f"Connect Timeout={settings.mssql_timeout};"
        )

    @contextmanager
    def get_connection(self):
        """Context manager trả về read-only connection"""
        conn = None
        try:
            conn = pyodbc.connect(self._connection_string, autocommit=False)
            conn.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            yield conn
        except pyodbc.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def execute_safe_query(self, sql: str, params: tuple = ()) -> list[dict]:
        """
        Execute SELECT query và trả về list of dicts.
        Tự động giới hạn kết quả theo settings.mssql_max_rows
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchmany(settings.mssql_max_rows)
            return [dict(zip(columns, row)) for row in rows]


# Singleton
db_pool = DatabasePool()
