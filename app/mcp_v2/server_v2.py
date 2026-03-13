"""
MCP Server v2 - Dùng Gemini API + SQL Post-processor
Pipeline: Intent → Table → Column → SQL (Gemini) → PostProcess → Execute
"""

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp"))

from intent_agent_v2 import intent_agent_v2
from table_agent_v2 import table_agent_v2
from column_agent_v2 import column_agent_v2
from sql_agent_v2 import sql_agent_v2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP v2 Text-to-SQL Server (Gemini)", version="2.0.0")

MCP_V2_PORT = int(os.getenv("MCP_V2_SERVER_PORT", "8002"))


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
    return {"status": "ok", "service": "mcp-v2-gemini"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    question = request.question.strip()
    tenant_id = int(request.tenant_id) if request.tenant_id.isdigit() else 0
    logger.info(f"[MCPv2] Query: {question} | tenant={tenant_id} | user={request.user_id} | manager={request.is_manager}")

    # Step 1: Intent
    intent = intent_agent_v2.classify(question)
    workspace = intent.get("workspace", "")
    if not workspace or workspace == "unknown":
        return QueryResponse(
            success=False, question=question, workspace="", tables=[],
            sql="", data=[], row_count=0, explanation="",
            error="Không xác định được workspace từ câu hỏi"
        )

    # Step 2: Tables
    table_result = table_agent_v2.select_tables(question, workspace)
    tables = table_result.get("tables", [])
    if not tables:
        return QueryResponse(
            success=False, question=question, workspace=workspace, tables=[],
            sql="", data=[], row_count=0, explanation="",
            error="Không xác định được tables liên quan"
        )

    # Step 3: Columns
    column_result = column_agent_v2.prune_columns(question, tables)
    schema_context = column_result.get("schema_context", "")

    # Step 4: SQL (Gemini generate) + Step 5: PostProcess + Step 6: Execute
    sql_result = sql_agent_v2.generate_and_execute(
        question, schema_context,
        tenant_id=tenant_id,
        employee_id=request.employee_id,
        is_manager=request.is_manager,
        department_ids=request.department_ids
    )

    logger.info(f"[MCPv2] Done | workspace={workspace} | rows={sql_result['row_count']} | error={sql_result['error'][:50] if sql_result['error'] else ''}")

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
    uvicorn.run(app, host="0.0.0.0", port=MCP_V2_PORT)
