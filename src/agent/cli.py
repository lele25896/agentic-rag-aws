"""Local chat with approval prompts: python -m agent.cli [--design react|plan] "question" """
import argparse
import sqlite3
import uuid

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from . import graph_plan, graph_react


def ask(agent, question: str, design: str, thread: str | None = None, input_fn=input):
    cfg = {"configurable": {"thread_id": thread or uuid.uuid4().hex}}
    payload = {"messages": [HumanMessage(question)]} if design == "react" else {"question": question}
    while True:
        out = agent.invoke(payload, cfg)
        if "__interrupt__" not in out:
            return out["messages"][-1].text if design == "react" else out["answer"]
        req = out["__interrupt__"][0].value
        ok = input_fn(f"approve {req['tool']}({req['args']})? [y/N] ").strip().lower() == "y"
        payload = Command(resume=ok)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--design", choices=["react", "plan"], default="react")
    ap.add_argument("--no-hitl", action="store_true")
    a = ap.parse_args()
    saver = SqliteSaver(sqlite3.connect("checkpoints.sqlite", check_same_thread=False))
    build = (graph_react if a.design == "react" else graph_plan).build
    print(ask(build(hitl=not a.no_hitl, checkpointer=saver), a.question, a.design))
