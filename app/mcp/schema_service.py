"""
Schema Service - Workspace routing + Schema cache
- Load workspace từ db_schema.json
- Cache columns của từng table (refresh mỗi 1 giờ)
- Routing: câu hỏi → workspace → tables liên quan
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from mssql_service import mssql_service

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "db_schema.json"
CACHE_TTL = 3600  # 1 giờ

# ==================== Workspaces ====================
# Chỉ bao gồm tables có giá trị business, loại bỏ ABP internal tables
WORKSPACES: dict[str, dict] = {
    "hr": {
        "description": "Nhân sự, nhân viên, phòng ban, chức vụ, chấm công, nghỉ phép, ca làm việc",
        "keywords": ["nhân viên", "nhân sự", "phòng ban", "chức vụ", "chấm công", "nghỉ phép", "ca làm", "employee", "department", "attendance", "leave"],
        "tables": [
            "Dms_Employee", "Dms_WorkDepartment", "Dms_WorkPosition",
            "Hrm_Attendancel", "Hrm_WorkShift", "Hrm_Devices", "Hrm_LeaveRequest"
        ]
    },
    "recruitment": {
        "description": "Tuyển dụng, tin tuyển dụng, kế hoạch tuyển dụng",
        "keywords": ["tuyển dụng", "tuyển", "ứng viên", "tin tuyển", "kế hoạch tuyển", "recruitment", "job", "hiring"],
        "tables": ["Hrm_JobPosting", "Rcm_RecruitmentPlan"]
    },
    "meeting": {
        "description": "Cuộc họp, lịch họp, biên bản họp, transcript, audio",
        "keywords": ["cuộc họp", "họp", "lịch họp", "biên bản", "transcript", "audio", "meeting", "assign"],
        "tables": [
            "Meeting_Meeting", "Meeting_AssginMeet",
            "Meeting_MeetingHistory", "Meeting_MeetAudio", "Meeting_Transcript"
        ]
    },
    "system_admin": {
        "description": "Người dùng, tài khoản, phân quyền, vai trò, tổ chức",
        "keywords": ["người dùng", "tài khoản", "phân quyền", "vai trò", "quyền", "user", "role", "permission", "tổ chức"],
        "tables": [
            "AbpUsers", "AbpRoles", "AbpPermissions",
            "AbpUserRoles", "AbpOrganizationUnits", "AbpUserOrganizationUnits"
        ]
    },
    "location": {
        "description": "Địa lý, quốc gia, tỉnh thành, quận huyện, phường xã, dân tộc",
        "keywords": ["tỉnh", "thành phố", "quận", "huyện", "phường", "xã", "quốc gia", "địa chỉ", "dân tộc", "city", "district", "ward"],
        "tables": ["Dms_Nation", "Dms_City", "Dms_District", "Dms_Ward", "Dms_Ethnic"]
    },
    "tenant": {
        "description": "Thông tin doanh nghiệp, công ty, tenant",
        "keywords": ["doanh nghiệp", "công ty", "tenant", "tổ chức", "thông tin công ty"],
        "tables": ["Dms_TenantInfo", "Dms_TenantInfo_Detail", "AbpTenants"]
    },
    "notification": {
        "description": "Thông báo hệ thống",
        "keywords": ["thông báo", "notification", "tin nhắn hệ thống"],
        "tables": ["Dms_SystemNotifications", "Dms_SystemNotificationUsers"]
    },
    "chatbot": {
        "description": "Lịch sử hội thoại AI chatbot",
        "keywords": ["hội thoại", "lịch sử chat", "chatbot", "ai chat", "conversation"],
        "tables": ["AIChatConversations", "AIChatMessages"]
    }
}


class SchemaService:
    def __init__(self):
        self._column_cache: dict[str, dict] = {}   # table_name → {columns, cached_at}
        self._schema_json: dict = {}
        self._load_schema_json()

    # ==================== Load schema JSON ====================

    def _load_schema_json(self):
        """Load db_schema.json vào memory."""
        try:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                self._schema_json = json.load(f)
            logger.info(f"Loaded schema from {SCHEMA_PATH}")
        except Exception as e:
            logger.error(f"Failed to load schema JSON: {e}")
            self._schema_json = {}

    def get_table_description(self, table_name: str) -> str:
        """Lấy description của table từ db_schema.json."""
        for group in self._schema_json.get("tables", []):
            for table in group.get("tables", []):
                if table["tableName"] == table_name:
                    return table.get("description", "")
        return ""

    # ==================== Column Cache ====================

    def _is_cache_expired(self, table_name: str) -> bool:
        if table_name not in self._column_cache:
            return True
        cached_at = self._column_cache[table_name].get("cached_at", 0)
        return (time.time() - cached_at) > CACHE_TTL

    def get_columns(self, table_name: str) -> list[dict]:
        """
        Lấy columns của table, dùng cache nếu còn hạn.
        Returns: [{"name": "Id", "type": "int", "nullable": "NO"}, ...]
        """
        if self._is_cache_expired(table_name):
            result = mssql_service.get_table_columns(table_name)
            if result["success"] and result["data"]:
                columns = [
                    {
                        "name": row["COLUMN_NAME"],
                        "type": row["DATA_TYPE"],
                        "nullable": row["IS_NULLABLE"]
                    }
                    for row in result["data"]
                ]
                self._column_cache[table_name] = {
                    "columns": columns,
                    "cached_at": time.time()
                }
                logger.info(f"Cached {len(columns)} columns for {table_name}")
            else:
                logger.warning(f"Failed to get columns for {table_name}")
                return []

        return self._column_cache[table_name].get("columns", [])

    def get_schema_for_tables(self, table_names: list[str]) -> str:
        """
        Tạo schema string cho danh sách tables → dùng làm context cho SQL Agent.
        Format:
            Table: Dms_Employee (Nhân viên)
            Columns: Id (int), FullName (nvarchar), ...
        """
        lines = []
        for table_name in table_names:
            description = self.get_table_description(table_name)
            columns = self.get_columns(table_name)

            if not columns:
                continue

            col_str = ", ".join(f"{c['name']} ({c['type']})" for c in columns)
            lines.append(f"Table: {table_name} ({description})")
            lines.append(f"Columns: {col_str}")
            lines.append("")

        return "\n".join(lines)

    # ==================== Workspace Routing ====================

    def get_workspace(self, workspace_name: str) -> dict | None:
        """Lấy thông tin 1 workspace."""
        return WORKSPACES.get(workspace_name)

    def get_all_workspaces(self) -> dict:
        """Lấy tất cả workspaces (dùng cho Intent Agent)."""
        return {
            name: {
                "description": ws["description"],
                "keywords": ws["keywords"]
            }
            for name, ws in WORKSPACES.items()
        }

    def get_tables_by_workspace(self, workspace_name: str) -> list[str]:
        """Lấy danh sách tables của 1 workspace."""
        ws = WORKSPACES.get(workspace_name)
        return ws["tables"] if ws else []

    def get_schema_by_workspace(self, workspace_name: str) -> str:
        """Lấy schema string của toàn bộ workspace → dùng cho Table Agent."""
        tables = self.get_tables_by_workspace(workspace_name)
        if not tables:
            return ""
        return self.get_schema_for_tables(tables)

    def invalidate_cache(self, table_name: str = None):
        """Xóa cache: 1 table hoặc toàn bộ."""
        if table_name:
            self._column_cache.pop(table_name, None)
            logger.info(f"Cache invalidated for {table_name}")
        else:
            self._column_cache.clear()
            logger.info("All schema cache invalidated")


# Singleton
schema_service = SchemaService()
