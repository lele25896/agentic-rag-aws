"""Design B: plan first, run each step with a ReAct executor, then synthesize.
Same tools + same HITL gate as design A; only the control flow differs."""
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .graph_react import SYSTEM, get_tools
from .llm import get_llm


class Plan(BaseModel):
    steps: list[str] = Field(description="1-4 short, self-contained steps; each needs at most a couple of tool calls")


class State(TypedDict, total=False):
    question: str
    plan: list[str]
    idx: int
    notes: list[str]
    answer: str


def build(hitl: bool = False, checkpointer=None):
    if hitl and checkpointer is None:
        raise ValueError("hitl needs a checkpointer (interrupt state must persist)")
    llm = get_llm()
    executor = create_react_agent(llm, get_tools(hitl), prompt=SYSTEM)

    def planner(s: State):
        p = llm.with_structured_output(Plan).invoke(
            "Break this question into the fewest steps that answer it. Tools available: "
            f"search_papers, extract_pdf, calc, web_search.\n\nQuestion: {s['question']}"
        )
        return {"plan": p.steps or [s["question"]], "idx": 0, "notes": []}

    def step(s: State):
        done = "\n".join(f"- {n}" for n in s["notes"]) or "(nothing yet)"
        task = f"Question: {s['question']}\nDone so far:\n{done}\n\nNow do this step: {s['plan'][s['idx']]}"
        out = executor.invoke({"messages": [HumanMessage(task)]})
        return {"notes": s["notes"] + [out["messages"][-1].text], "idx": s["idx"] + 1}

    def synth(s: State):
        notes = "\n".join(f"- {n}" for n in s["notes"])
        a = llm.invoke(f"Question: {s['question']}\n\nFindings:\n{notes}\n\nWrite the final concise answer, citing paper ids.")
        return {"answer": a.text}

    g = StateGraph(State)
    g.add_node("planner", planner)
    g.add_node("step", step)
    g.add_node("synth", synth)
    g.add_edge(START, "planner")
    g.add_edge("planner", "step")
    g.add_conditional_edges("step", lambda s: "step" if s["idx"] < len(s["plan"]) else "synth")
    g.add_edge("synth", END)
    return g.compile(checkpointer=checkpointer)
