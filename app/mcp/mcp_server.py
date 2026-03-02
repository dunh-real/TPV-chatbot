"""
MCP Server - Cung cấp tools cho LLM truy vấn MSSQL
Mỗi tool đều enforce department_id filter để đảm bảo data isolation.

Cách hoạt động:
1. LLM nhận câu hỏi user + department_id từ context
2. LLM chọn tool phù hợp, truyền department_id bắt buộc
3. Tool execute query với WHERE DepartmentID = ? hardcode
4. Kết quả trả về cho LLM tổng hợp thành câu trả lời

Security:
- Mọi tool đều BẮT BUỘC department_id param → data isolation
- SQL được validate trước khi execute (chặn write operations)
- Connection là read-only (ApplicationIntent=ReadOnly)
- Audit log mọi truy vấn
- Giới hạn số rows trả về
"""

import json
import logging
from mcp.server.fastmcp import FastMCP
from app.mcp.db_connection import db_pool
from app.mcp.security import validate_sql_safety, audit_log

logger = logging.getLogger(__name__)

# Khởi tạo MCP Server
mcp_server = FastMCP(
    name="erp-database-tools",
    instructions="""
    Bạn có quyền truy cập database ERP thông qua các tools bên dưới.
    MỌI truy vấn PHẢI kèm department_id để đảm bảo phân quyền dữ liệu.
    Chỉ trả về dữ liệu thuộc phòng ban của người hỏi.
    Nếu không có department_id, TỪ CHỐI truy vấn.
    """,
)


# ==================== MCP TOOLS ====================

@mcp_server.tool()
def query_department_employees(
    department_id: int,
    tenant_id: str,
    search_name: str = "",
) -> str:
    """
    Tìm kiếm nhân viên trong phòng ban.
    Chỉ trả về nhân viên thuộc department_id được chỉ định.

    Args:
        department_id: ID phòng ban (BẮT BUỘC - dùng để phân quyền)
        tenant_id: ID tenant/công ty
        search_name: Tên nhân viên cần tìm (tùy chọn, để trống = lấy tất cả)
    """
    try:
        sql = """
            SELECT e.Code, e.FullName, e.Email, e.Phone, 
                   e.Gender, e.Address,
                   d.Name AS DepartmentName,
                   p.Name AS PositionName
            FROM Dms_Employee e
            LEFT JOIN Dms_WorkDepartment d ON e.WorkDepartmentId = d.Id
            LEFT JOIN Dms_WorkPosition p ON e.WorkPositionId = p.Id
            WHERE e.WorkDepartmentId = ? 
              AND e.TenantId = ?
              AND e.IsDeleted = 0
        """
        params = [department_id, int(tenant_id)]

        if search_name:
            sql += " AND e.FullName LIKE ?"
            params.append(f"%{search_name}%")

        sql += " ORDER BY e.FullName"

        results = db_pool.execute_safe_query(sql, tuple(params))

        audit_log(
            user_id="", tenant_id=tenant_id,
            department_id=department_id,
            tool_name="query_department_employees",
            parameters={"search_name": search_name},
            success=True,
        )

        if not results:
            return json.dumps({"message": "Không tìm thấy nhân viên nào.", "data": []}, ensure_ascii=False)

        return json.dumps({"count": len(results), "data": results}, ensure_ascii=False, default=str)

    except Exception as e:
        audit_log(
            user_id="", tenant_id=tenant_id,
            department_id=department_id,
            tool_name="query_department_employees",
            parameters={"search_name": search_name},
            success=False, error=str(e),
        )
        return json.dumps({"error": f"Lỗi truy vấn: {str(e)}"}, ensure_ascii=False)


@mcp_server.tool()
def query_department_documents(
    department_id: int,
    tenant_id: str,
    keyword: str = "",
    limit: int = 20,
) -> str:
    """
    Tìm kiếm văn bản/tài liệu thuộc phòng ban.

    Args:
        department_id: ID phòng ban (BẮT BUỘC)
        tenant_id: ID tenant/công ty
        keyword: Từ khóa tìm kiếm trong tiêu đề tài liệu (tùy chọn)
        limit: Số lượng kết quả tối đa (mặc định 20)
    """
    try:
        sql = """
            SELECT TOP (?) d.Id, d.Code, d.Name, d.Description,
                   d.CreationTime, d.Status
            FROM Dms_Document d
            WHERE d.DepartmentId = ?
              AND d.TenantId = ?
              AND d.IsDeleted = 0
        """
        params = [min(limit, 50), department_id, int(tenant_id)]

        if keyword:
            sql += " AND (d.Name LIKE ? OR d.Description LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        sql += " ORDER BY d.CreationTime DESC"

        results = db_pool.execute_safe_query(sql, tuple(params))

        audit_log(
            user_id="", tenant_id=tenant_id,
            department_id=department_id,
            tool_name="query_department_documents",
            parameters={"keyword": keyword, "limit": limit},
            success=True,
        )

        if not results:
            return json.dumps({"message": "Không tìm thấy tài liệu nào.", "data": []}, ensure_ascii=False)

        return json.dumps({"count": len(results), "data": results}, ensure_ascii=False, default=str)

    except Exception as e:
        audit_log(
            user_id="", tenant_id=tenant_id,
            department_id=department_id,
            tool_name="query_department_documents",
            parameters={"keyword": keyword},
            success=False, error=str(e),
        )
        return json.dumps({"error": f"Lỗi truy vấn: {str(e)}"}, ensure_ascii=False)


@mcp_server.tool()
def query_department_statistics(
    department_id: int,
    tenant_id: str,
    stat_type: str = "summary",
) -> str:
    """
    Lấy thống kê tổng quan của phòng ban.

    Args:
        department_id: ID phòng ban (BẮT BUỘC)
        tenant_id: ID tenant/công ty
        stat_type: Loại thống kê - "summary" (tổng quan), "headcount" (nhân sự), "documents" (tài liệu)
    """
    try:
        tid = int(tenant_id)

        if stat_type == "headcount":
            sql = """
                SELECT 
                    COUNT(*) AS TotalEmployees,
                    SUM(CASE WHEN Gender = 1 THEN 1 ELSE 0 END) AS Male,
                    SUM(CASE WHEN Gender = 0 THEN 1 ELSE 0 END) AS Female
                FROM Dms_Employee
                WHERE WorkDepartmentId = ? AND TenantId = ? AND IsDeleted = 0
            """
            params = (department_id, tid)

        elif stat_type == "documents":
            sql = """
                SELECT 
                    COUNT(*) AS TotalDocuments,
                    SUM(CASE WHEN Status = 1 THEN 1 ELSE 0 END) AS Approved,
                    SUM(CASE WHEN Status = 0 THEN 1 ELSE 0 END) AS Pending
                FROM Dms_Document
                WHERE DepartmentId = ? AND TenantId = ? AND IsDeleted = 0
            """
            params = (department_id, tid)

        else:  # summary
            sql = """
                SELECT 
                    d.Name AS DepartmentName,
                    (SELECT COUNT(*) FROM Dms_Employee 
                     WHERE WorkDepartmentId = ? AND TenantId = ? AND IsDeleted =  n ) AS EmployeeCount,
                    (SELECT COUNT(*) FROM Dms_Document 
                     WHERE DepartmentId = ? AND TenantId = ? AND IsDeleted = 0) AS DocumentCount
                FROM Dms_WorkDepartment d
                WHERE d.Id = ? AND d.TenantId = ?
            """
            params = (department_id, tid, department_id, tid, department_id, tid)

        results = db_pool.execute_safe_query(sql, params)

        audit_log(
            user_id="", tenant_id=tenant_id,
            department_id=department_id,
            tool_name="query_department_statistics",
            parameters={"stat_type": stat_type},
            success=True,
        )

        return json.dumps({"stat_type": stat_type, "data": results}, ensure_ascii=False, default=str)

    except Exception as e:
        audit_log(
            user_id="", tenant_id=tenant_id,
            department_id=department_id,
            tool_name="query_department_statistics",
            parameters={"stat_type": stat_type},
            success=False, error=str(e),
        )
        return json.dumps({"error": f"Lỗi truy vấn: {str(e)}"}, ensure_ascii=False)


@mcp_server.tool()
def query_custom(
    department_id: int,
    tenant_id: str,
    description: str,
) -> str:
    """
    Tool linh hoạt - mô tả dữ liệu cần lấy bằng ngôn ngữ tự nhiên.
    Tool này sẽ KHÔNG tự generate SQL. Thay vào đó, nó cung cấp schema 
    các bảng được phép truy cập để LLM có thể tham khảo.

    Args:
        department_id: ID phòng ban (BẮT BUỘC)
        tenant_id: ID tenant/công ty
        description: Mô tả dữ liệu cần lấy
    """
    # Trả về schema để LLM biết cấu trúc DB
    allowed_schema = {
        "message": "Dưới đây là schema các bảng bạn được phép truy cập. "
                   "Hãy dùng các tool cụ thể (query_department_employees, "
                   "query_department_documents, query_department_statistics) "
                   "để lấy dữ liệu.",
        "available_tables": {
            "Dms_Employee": {
                "columns": ["Code", "FullName", "Email", "Phone", "Gender", 
                           "Address", "WorkDepartmentId", "WorkPositionId", "TenantId"],
                "filter": "WorkDepartmentId = department_id AND TenantId = tenant_id",
            },
            "Dms_Document": {
                "columns": ["Id", "Code", "Name", "Description", "Status",
                           "DepartmentId", "CreationTime", "TenantId"],
                "filter": "DepartmentId = department_id AND TenantId = tenant_id",
            },
            "Dms_WorkDepartment": {
                "columns": ["Id", "Name", "Code", "TenantId"],
                "filter": "Id = department_id AND TenantId = tenant_id",
            },
        },
        "security_note": "Mọi query PHẢI filter theo department_id và tenant_id",
        "user_request": description,
        "department_id": department_id,
        "tenant_id": tenant_id,
    }

    audit_log(
        user_id="", tenant_id=tenant_id,
        department_id=department_id,
        tool_name="query_custom",
        parameters={"description": description},
        success=True,
    )

    return json.dumps(allowed_schema, ensure_ascii=False)
