# Phase 4 — MCP server

Code: [mcp_server.py](../src/agent/mcp_server.py), [tests/test_mcp.py](../tests/test_mcp.py).

## The problem it solves
MCP (Model Context Protocol) lets any MCP client (Claude Desktop, Claude Code, an IDE) call our tools
without knowing anything about LangGraph. It also shows the same tool layer serving two front-ends.

## What exists now
`FastMCP("papers")` over stdio; for each tool in `ALL_TOOLS` it does
`mcp.add_tool(t.func, name=t.name, description=t.description)`. The type hints and docstrings of the
plain functions become the JSON schema and the tool description. About 10 lines. No approval gate:
MCP clients already ask the user before every tool call.

## Verification
`tests/test_mcp.py` spawns the server as a subprocess, runs `initialize`, `list_tools` (asserts the four names)
and `call_tool("calc", "6*7")` == `42`. Passed.

## Use it from Claude Code / Desktop
```json
{ "mcpServers": { "papers": {
  "command": "C:/Users/gabri/miniconda3/envs/torch_env/python.exe",
  "args": ["-m", "agent.mcp_server"],
  "env": { "PYTHONPATH": "<repo>/src", "LLM_BACKEND": "ollama" } } } }
```
`extract_pdf` needs a running Ollama/Bedrock LLM; `search_papers` needs `index/<backend>` built.
