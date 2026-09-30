"""Design A: prebuilt ReAct loop + optional human approval on gated tools."""
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from langgraph.types import interrupt

from .llm import get_llm
from .tools import ALL_TOOLS, GATED

SYSTEM = (
    "You answer questions about a corpus of research papers. Use search_papers first for anything "
    "about the papers, calc for any arithmetic, extract_pdf for structured fields from one paper, "
    "web_search only for facts outside the corpus. Cite paper ids. Be concise."
)


def gate(t):
    """Pause the graph for a human yes/no before running the tool."""
    def run(**kwargs):
        if interrupt({"tool": t.name, "args": kwargs}) not in (True, "yes", "approve", "approved"):
            return "denied by the user; answer without this tool"
        return t.invoke(kwargs)

    return StructuredTool.from_function(
        func=run, name=t.name, description=t.description, args_schema=t.args_schema
    )


def get_tools(hitl: bool):
    return [gate(t) if hitl and t.name in GATED else t for t in ALL_TOOLS]


def build(hitl: bool = False, checkpointer=None):
    if hitl and checkpointer is None:
        raise ValueError("hitl needs a checkpointer (interrupt state must persist)")
    return create_react_agent(get_llm(), get_tools(hitl), prompt=SYSTEM, checkpointer=checkpointer)
