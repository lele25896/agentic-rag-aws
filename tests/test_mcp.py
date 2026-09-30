"""Spawn the MCP server over stdio, list tools, call calc: python -m pytest tests/test_mcp.py -q"""
import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SRC = str(Path(__file__).resolve().parents[1] / "src")


async def _run():
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "agent.mcp_server"], env={**os.environ, "PYTHONPATH": SRC}
    )
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        names = {t.name for t in (await s.list_tools()).tools}
        res = await s.call_tool("calc", {"expression": "6*7"})
        return names, res.content[0].text


def test_mcp_lists_and_calls():
    names, out = asyncio.run(_run())
    assert names == {"search_papers", "extract_pdf", "calc", "web_search"}
    assert out == "42"
