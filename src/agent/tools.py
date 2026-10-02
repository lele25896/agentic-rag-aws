"""Plain tool functions, shared by the LangGraph agents and the MCP server."""
import ast
import math
import operator as op
import re

from langchain_core.tools import tool
from pydantic import create_model

from .llm import DATA_DIR, get_llm
from .retrieval import get_store

_BIN = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
        ast.Pow: op.pow, ast.Mod: op.mod, ast.FloorDiv: op.floordiv}
_UN = {ast.USub: op.neg, ast.UAdd: op.pos}
_FN = {n: getattr(math, n) for n in
       ("sqrt", "log", "log2", "log10", "exp", "sin", "cos", "tan", "floor", "ceil")}
_FN.update(abs=abs, round=round, min=min, max=max)
_CONST = {"pi": math.pi, "e": math.e}


def _ev(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.Name) and n.id in _CONST:
        return _CONST[n.id]
    if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
        a, b = _ev(n.left), _ev(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 1000:  # no 9**9**9 CPU bombs
            raise ValueError("exponent too large")
        return _BIN[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and type(n.op) in _UN:
        return _UN[type(n.op)](_ev(n.operand))
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FN and not n.keywords:
        return _FN[n.func.id](*[_ev(a) for a in n.args])
    raise ValueError("unsupported expression")


@tool
def calc(expression: str) -> str:
    """Evaluate an arithmetic expression, e.g. '0.35 * 1200 / 7' or 'sqrt(2) * 3'.
    Supports + - * / ** % //, parentheses, pi, e, sqrt/log/exp/sin/cos/min/max/round/abs."""
    try:
        return str(_ev(ast.parse(expression.strip(), mode="eval").body))
    except Exception as exc:
        return f"error: {exc}"


@tool
def search_papers(query: str, k: int = 4) -> str:
    """Semantic search over the local corpus of research papers. Returns the top-k
    passages, each tagged with its paper id (source) and page."""
    docs = get_store().similarity_search(query, k=k)
    return "\n\n".join(f"[{d.metadata['source']} p.{d.metadata['page']}] {d.page_content}" for d in docs)


@tool
def extract_pdf(source: str, fields: list[str]) -> str:
    """Extract named fields (e.g. ['title', 'main_contribution', 'dataset']) from one paper.
    `source` is a paper id as shown in search_papers results, e.g. '2504.07877v1'."""
    path = (DATA_DIR / f"{source}.pdf").resolve()
    if path.parent != DATA_DIR.resolve() or not path.is_file():  # trust boundary: model-supplied path
        return f"error: unknown paper '{source}'"
    import pymupdf

    with pymupdf.open(path) as pdf:
        text = "".join(p.get_text() for p in list(pdf)[:4])[:8000]  # ponytail: first 4 pages, add map-reduce if fields live deeper
    # model-supplied names become JSON-schema keys; Bedrock rejects anything outside [a-zA-Z0-9_.-]{1,64}
    names = [re.sub(r"[^a-zA-Z0-9_.-]+", "_", f).strip("_")[:64] or "field" for f in fields]
    schema = create_model("Extraction", **{n: (str | None, None) for n in dict.fromkeys(names)})
    try:
        res = get_llm().with_structured_output(schema).invoke(
            f"Extract these fields from the paper excerpt. Use null if absent.\n\n{text}"
        )
    except Exception as exc:  # report to the agent instead of crashing the whole run
        return f"error: extraction failed: {exc}"[:300]
    return res.model_dump_json()


@tool
def web_search(query: str) -> str:
    """Search the public web (DuckDuckGo). Use only for facts not in the local papers."""
    from ddgs import DDGS

    try:
        hits = DDGS().text(query, max_results=4)
    except Exception as exc:
        return f"error: {exc}"
    return "\n\n".join(f"{h['title']} ({h['href']}): {h['body']}" for h in hits) or "no results"


ALL_TOOLS = [search_papers, extract_pdf, calc, web_search]
GATED = {"extract_pdf", "web_search"}  # human-in-the-loop approval (see graph_react.py)
