"""
MCP Server - FastAPI server expose Text-to-SQL pipeline
Chạy riêng ở port 8001, chatbot gọi vào để query DB
"""

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Add mcp dir to path để import các agents
sys.path.insert(0, str(Path(__file__).parent))

from intent_agent import intent_agent
from table_agent import table_agent
from column_agent import column_agent
from sql_agent import sql_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Text-to-SQL Server", version="1.0.0")

MCP_PORT = int(os.getenv("MCP_SERVER_PORT", "8001"))


class QueryRequest(BaseModel):
    question: str
    tenant_id: str = "0"
    user_id: str = "0"
    role_id: int = 0
    employee_id: int = 0
    is_manager: bool = False
    department_ids: list[int] = []


class QueryResponse(BaseModel):
    success: bool
    question: str
    workspace: str
    tables: list[str]
    sql: str
    data: list[dict]
    row_count: int
    explanation: str
    error: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-sql-server"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    question = request.question.strip()
    tenant_id = int(request.tenant_id) if request.tenant_id.isdigit() else 0
    logger.info(f"[MCP] Query: {question} | tenant={tenant_id} | user={request.user_id} | is_manager={request.is_manager} | dept_ids={request.department_ids}")

    # Step 1: Intent
    intent = intent_agent.classify(question)
    workspace = intent.get("workspace", "")
    if not workspace:
        return QueryResponse(
            success=False, question=question, workspace="", tables=[],
            sql="", data=[], row_count=0, explanation="",
            error="Không xác định được workspace từ câu hỏi"
        )

    # Step 2: Tables
    table_result = table_agent.select_tables(question, workspace)
    tables = table_result.get("tables", [])
    if not tables:
        return QueryResponse(
            success=False, question=question, workspace=workspace, tables=[],
            sql="", data=[], row_count=0, explanation="",
            error="Không xác định được tables liên quan"
        )

    # Step 3: Columns
    column_result = column_agent.prune_columns(question, tables)
    schema_context = column_result.get("schema_context", "")

    # Step 4: SQL (truyền tenant_id + access control info)
    sql_result = sql_agent.generate_and_execute(
        question, schema_context,
        tenant_id=tenant_id,
        employee_id=request.employee_id,
        is_manager=request.is_manager,
        department_ids=request.department_ids
    )

    logger.info(f"[MCP] Done | workspace={workspace} | rows={sql_result['row_count']} | error={sql_result['error'][:50] if sql_result['error'] else ''}")

    return QueryResponse(
        success=sql_result["success"],
        question=question,
        workspace=workspace,
        tables=tables,
        sql=sql_result["sql"],
        data=sql_result["data"],
        row_count=sql_result["row_count"],
        explanation=sql_result["explanation"],
        error=sql_result["error"]
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=MCP_PORT)
