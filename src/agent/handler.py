"""Lambda Function URL entrypoint.
  POST /chat     {"question": str, "design": "react"|"plan"}   -> {"status": "done", "answer"} | {"status": "needs_approval", "thread_id", "pending": {tool, args}}
  POST /approve  {"thread_id": str, "approve": bool}           -> same shape (resumes the paused graph)
Every request needs header x-api-key == $API_KEY. Paused state lives in DynamoDB ($CHECKPOINT_TABLE),
so /approve can land on a different Lambda instance than /chat."""
import hmac
import json
import os
import uuid

from langchain_core.messages import HumanMessage
from langgraph.types import Command

_agents: dict = {}


def _agent(design: str):
    if design not in _agents:
        from . import graph_plan, graph_react

        table = os.environ.get("CHECKPOINT_TABLE")
        if table:
            from langgraph_checkpoint_aws import DynamoDBSaver

            saver = DynamoDBSaver(table_name=table, region_name=os.environ.get("AWS_REGION"), ttl_seconds=86400)
        else:  # local/dev only: state is per-process
            from langgraph.checkpoint.memory import InMemorySaver

            saver = InMemorySaver()
        _agents[design] = (graph_react if design == "react" else graph_plan).build(hitl=True, checkpointer=saver)
    return _agents[design]


def _reply(code: int, body: dict) -> dict:
    return {"statusCode": code, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def _drive(thread_id: str, payload) -> dict:
    design = thread_id.split(":", 1)[0]
    out = _agent(design).invoke(payload, {"configurable": {"thread_id": thread_id}})
    if "__interrupt__" in out:
        return {"status": "needs_approval", "thread_id": thread_id, "pending": out["__interrupt__"][0].value}
    answer = out["messages"][-1].text if design == "react" else out["answer"]
    return {"status": "done", "thread_id": thread_id, "answer": answer}


def handler(event, context=None):
    key = os.environ.get("API_KEY", "")
    given = (event.get("headers") or {}).get("x-api-key", "")
    if not key or not hmac.compare_digest(given.encode(), key.encode()):
        return _reply(401, {"error": "unauthorized"})
    try:
        body = json.loads(event.get("body") or "{}")
        route = event.get("rawPath", "")
        if route == "/chat":
            design = body.get("design", "react")
            if design not in ("react", "plan") or not isinstance(body.get("question"), str):
                return _reply(400, {"error": "need question:str and design in react|plan"})
            thread = f"{design}:{uuid.uuid4().hex}"
            payload = {"messages": [HumanMessage(body["question"])]} if design == "react" else {"question": body["question"]}
            return _reply(200, _drive(thread, payload))
        if route == "/approve":
            thread = body.get("thread_id", "")
            if thread.split(":", 1)[0] not in ("react", "plan") or not isinstance(body.get("approve"), bool):
                return _reply(400, {"error": "need thread_id and approve:bool"})
            return _reply(200, _drive(thread, Command(resume=body["approve"])))
        return _reply(404, {"error": "not found"})
    except json.JSONDecodeError:
        return _reply(400, {"error": "invalid json"})
