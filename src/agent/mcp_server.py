"""Expose the same tools over MCP (stdio): python -m agent.mcp_server
No approval gate here: the MCP client (Claude Desktop/Code) asks the user before each tool call."""
from mcp.server.fastmcp import FastMCP

from .tools import ALL_TOOLS

mcp = FastMCP("papers")
for t in ALL_TOOLS:
    mcp.add_tool(t.func, name=t.name, description=t.description)

if __name__ == "__main__":
    mcp.run()
