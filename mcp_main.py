"""
MCP Server Entry Point
Chạy riêng biệt với FastAPI main app.

Usage: python mcp_main.py
"""

from app.mcp.mcp_server import mcp_server
from app.core.config import settings


if __name__ == "__main__":
    print(f"🔧 MCP Server đang chạy tại http://0.0.0.0:{settings.mcp_server_port}/mcp")
    mcp_server.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=settings.mcp_server_port,
    )
