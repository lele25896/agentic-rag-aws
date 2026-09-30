# Phase 2 — Human-in-the-loop + plan-and-execute (design B)

Code: [graph_react.py](../src/agent/graph_react.py) (`gate`), [graph_plan.py](../src/agent/graph_plan.py), [cli.py](../src/agent/cli.py).

## The problem it solves
1. Some tools leave the trust boundary or spend money (`web_search`, `extract_pdf`). A human should approve them.
2. The eval needs **two genuinely different agent designs** to compare.

## HITL: how it works
`gate(tool)` wraps a tool so that, before running, it calls LangGraph `interrupt({"tool", "args"})`.
The graph **pauses and persists its state in the checkpointer**; the caller resumes with
`Command(resume=True|False)`. Denied -> the tool returns "denied by the user" and the model answers without it.
- Local: `SqliteSaver` (`checkpoints.sqlite`). AWS: `DynamoDBSaver` (Phase 5). That is why the paused state
  survives a different Lambda instance serving `/approve`.
- The gate lives in the *agent layer*, not in `tools.py`, so the MCP server is unaffected (MCP clients ask the user).
- `build(hitl=True)` without a checkpointer raises: an interrupt without persistence silently loses the run.

## Design B: plan -> step* -> synthesize
`StateGraph` with 3 nodes: `planner` (structured output `Plan{steps}`), `step` (runs a ReAct executor on the
current step plus the notes so far; loops through a conditional edge), `synth` (final answer from the notes).
Same tools, same gate; only the control flow differs, so the eval isolates that variable.
The executor is invoked inside a node and interrupts still bubble up to the outer graph (verified below).

## Verification
Question "Extract title and main contribution from 2504.07877v1, then 17*23", HITL on, auto-answering `y`:

| design | result | time | approvals asked |
|---|---|---|---|
| react | correct title + contribution, 391 | 28 s | 1 |
| plan | same | 44 s | 1 |

Both paused at `extract_pdf`, resumed, and answered correctly.

## Trade-off to expect
B costs more LLM calls (planner + synth + executor) but may be more reliable on multi-part questions.
Phase 3 puts numbers on that.
