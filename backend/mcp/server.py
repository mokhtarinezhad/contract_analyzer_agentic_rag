"""
MCP (Model Context Protocol) Server.

Exposes the Contract Analyzer as tool endpoints consumable by
any MCP-compatible client (Claude Desktop, Cursor, etc.).

Tools exposed:
  - analyze_contract : Upload and analyse a PDF contract
  - get_results      : Retrieve results for a previously submitted analysis
  - query_contract   : Ask a free-form question about an analysed contract

Run with:
    python -m backend.mcp.server

Or add to Claude Desktop's mcp_servers config:
{
  "contract-analyzer": {
    "command": "python",
    "args": ["-m", "backend.mcp.server"],
    "env": {"ANTHROPIC_API_KEY": "..."}
  }
}
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import tempfile
import uuid
from pathlib import Path

from backend.config import settings

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from mcp.server import Server  # type: ignore
    from mcp.server.stdio import stdio_server  # type: ignore
    from mcp import types as mcp_types  # type: ignore
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("WARNING: 'mcp' package not installed. Install with: pip install mcp>=1.2.0", flush=True)

from backend.observability.logger import configure_logging, get_logger
from backend.observability.metrics_store import init_db

configure_logging()
logger = get_logger(__name__)


def create_mcp_server():
    """Build and return the MCP server with registered tools."""
    if not MCP_AVAILABLE:
        raise ImportError("mcp package required. pip install mcp>=1.2.0")

    server = Server("contract-analyzer")
    init_db()

    # ── Tool: analyze_contract ────────────────────────────────────────────

    @server.list_tools()
    async def list_tools():
        return [
            mcp_types.Tool(
                name="analyze_contract",
                description=(
                    "Upload and analyse a PDF contract for compliance against 5 security "
                    "requirements: Password Management, IT Asset Management, Security Training, "
                    "Data in Transit Encryption, and Network Authentication. "
                    "Returns structured JSON with compliance state, confidence, quotes, and rationale."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pdf_base64": {
                            "type": "string",
                            "description": "Base64-encoded PDF content",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Original filename for display purposes",
                        },
                    },
                    "required": ["pdf_base64", "filename"],
                },
            ),
            mcp_types.Tool(
                name="get_analysis_results",
                description="Retrieve the results of a previously submitted contract analysis.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "Job ID returned by analyze_contract",
                        },
                    },
                    "required": ["job_id"],
                },
            ),
            mcp_types.Tool(
                name="query_contract",
                description=(
                    "Ask a free-form question about an already-analysed contract. "
                    "Uses semantic search over the contract's vector store."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "contract_id": {
                            "type": "string",
                            "description": "Contract ID from a completed analysis",
                        },
                        "question": {
                            "type": "string",
                            "description": "Free-form question about the contract",
                        },
                    },
                    "required": ["contract_id", "question"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        logger.info("mcp_tool_call", tool=name, args_keys=list(arguments.keys()))

        if name == "analyze_contract":
            return await _tool_analyze_contract(arguments)
        elif name == "get_analysis_results":
            return await _tool_get_results(arguments)
        elif name == "query_contract":
            return await _tool_query_contract(arguments)
        else:
            return [mcp_types.TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


# ─────────────────────────────────────────────
# Tool implementations
# ─────────────────────────────────────────────

async def _tool_analyze_contract(args: dict):
    """Decode PDF, run analysis via the FastAPI backend."""
    if not MCP_AVAILABLE:
        return []

    import httpx

    pdf_b64 = args.get("pdf_base64", "")
    filename = args.get("filename", "contract.pdf")

    try:
        pdf_bytes = base64.b64decode(pdf_b64)
    except Exception as exc:
        return [mcp_types.TextContent(type="text", text=f"Invalid base64: {exc}")]

    api_base = settings.api_base_url

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            resp = await client.post(
                f"{api_base}/analyze",
                files={"file": (filename, pdf_bytes, "application/pdf")},
            )
            resp.raise_for_status()
            data = resp.json()
            return [mcp_types.TextContent(
                type="text",
                text=json.dumps(data, indent=2),
            )]
        except Exception as exc:
            return [mcp_types.TextContent(type="text", text=f"API error: {exc}")]


async def _tool_get_results(args: dict):
    if not MCP_AVAILABLE:
        return []

    import httpx

    job_id = args.get("job_id", "")
    api_base = settings.api_base_url

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{api_base}/results/{job_id}")
            resp.raise_for_status()
            data = resp.json()
            return [mcp_types.TextContent(
                type="text",
                text=json.dumps(data, indent=2),
            )]
        except Exception as exc:
            return [mcp_types.TextContent(type="text", text=f"API error: {exc}")]


async def _tool_query_contract(args: dict):
    if not MCP_AVAILABLE:
        return []

    import httpx

    contract_id = args.get("contract_id", "")
    question = args.get("question", "")
    api_base = settings.api_base_url

    payload = {"contract_id": contract_id, "message": question, "history": []}

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(f"{api_base}/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return [mcp_types.TextContent(
                type="text",
                text=data.get("reply", "No response"),
            )]
        except Exception as exc:
            return [mcp_types.TextContent(type="text", text=f"API error: {exc}")]


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

async def main():
    server = create_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    if not MCP_AVAILABLE:
        print("Install mcp: pip install mcp>=1.2.0")
        sys.exit(1)
    asyncio.run(main())
