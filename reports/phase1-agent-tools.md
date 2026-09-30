# Phase 1 — Tools + ReAct agent (design A)

Code: [tools.py](../src/agent/tools.py), [graph_react.py](../src/agent/graph_react.py), [tests/test_tools.py](../tests/test_tools.py).

## The problem it solves
Turn the RAG pipeline into an **agent**: the model decides *which* tool to call (paper search, extraction,
math, web) instead of always doing retrieve-then-generate.

## What exists now
| Tool | What it does | Safety |
|---|---|---|
| `search_papers(query, k)` | FAISS similarity search, returns `[paper page] passage` blocks | read-only |
| `extract_pdf(source, fields)` | First 4 pages -> LLM `with_structured_output` on a **dynamically built pydantic model** (one optional str per requested field) | `source` is resolved inside `DATA_DIR`; path traversal returns an error (test) |
| `calc(expression)` | `ast`-walking evaluator: + - * / ** % //, pi/e, sqrt/log/exp/trig/min/max/round/abs | No `eval`; exponent capped at 1000 so `9**9**9` cannot burn CPU (test) |
| `web_search(query)` | DuckDuckGo via `ddgs`, top 4 hits | errors returned as text, never raised into the graph |

Design A = `langgraph.prebuilt.create_react_agent(llm, tools, prompt=SYSTEM)`: the model loops
*think -> tool call -> observe* until it answers. About 25 lines of our own code.

## Why plain functions + `@tool`
The same four functions are reused by the MCP server (Phase 4). Nothing in `tools.py` knows about
LangGraph state, approvals or transport; those are layered on top.

## Verification
- `pytest tests/test_tools.py`: 3 passed (calc happy path, calc rejects code injection and bombs, path traversal).
- Live smoke on Ollama: "Which paper studies regular black holes, and what is the square root of 1764?" ->
  correct paper id (2509.12469v2) and 42, using `search_papers` + `calc`, 37 s.

## Known limits (marked `ponytail:` in code)
- `extract_pdf` reads only the first 4 pages / 8000 chars: fine for title/authors/keywords, wrong for
  fields deep in the paper. Upgrade: map-reduce over pages.
- Tool-choice quality depends on the model; measured in Phase 3, not assumed.
