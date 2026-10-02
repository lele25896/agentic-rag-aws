"""Eval: 30 tasks x 2 agent designs -> evals/raw/<backend>-<design>.jsonl -> evals/results.md
  python evals/run.py run --design react|plan|both [--limit N]   (resumable: skips done ids)
  python evals/run.py report                                     (aggregate raw/*.jsonl)
HITL is off here (auto-approve): approvals would only add human wait time to the latency numbers."""
import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from langchain_core.callbacks import BaseCallbackHandler, UsageMetadataCallbackHandler  # noqa: E402
from langchain_core.messages import HumanMessage  # noqa: E402

from agent import graph_plan, graph_react  # noqa: E402
from agent.llm import BACKEND, get_llm  # noqa: E402

RAW = HERE / "raw"
# USD per 1M tokens (in, out); local Ollama is free. ponytail: one Bedrock price (EU regional profile: +10% over global), update if BEDROCK_MODEL changes
PRICE = {"bedrock": (1.1, 5.5), "ollama": (0.0, 0.0)}[BACKEND]


class ToolLog(BaseCallbackHandler):
    def __init__(self):
        self.tools = []

    def on_tool_start(self, serialized, input_str, **kw):
        self.tools.append(kw.get("name") or serialized.get("name"))


def numbers(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?", text) if x.strip(",")]


def judge(question: str, reference: str, answer: str) -> bool:
    v = get_llm().invoke(
        f"Question: {question}\nReference answer: {reference}\nCandidate answer: {answer}\n\n"
        "Does the candidate convey the same key facts as the reference (extra detail is fine)? "
        "Reply with exactly one word: CORRECT or INCORRECT."
    ).text
    return "INCORRECT" not in v.upper() and "CORRECT" in v.upper()


def score(task: dict, answer: str) -> bool:
    c = task["check"]
    if c["type"] == "number":
        return any(abs(n - c["value"]) <= 1e-2 * max(1.0, abs(c["value"])) for n in numbers(answer))
    if c["type"] == "contains":
        return all(s.lower() in answer.lower() for s in c["value"])
    return judge(task["question"], c["value"], answer)


def run_one(agent, design: str, task: dict) -> dict:
    log, usage = ToolLog(), UsageMetadataCallbackHandler()
    cfg = {"callbacks": [log, usage], "recursion_limit": 40}
    t0 = time.time()
    try:
        if design == "react":
            out = agent.invoke({"messages": [HumanMessage(task["question"])]}, cfg)
            answer = out["messages"][-1].text
        else:
            answer = agent.invoke({"question": task["question"]}, cfg)["answer"]
        err = None
    except Exception as exc:  # a crashed task counts as a failure, not an aborted eval
        answer, err = "", f"{type(exc).__name__}: {exc}"[:300]
    secs = time.time() - t0
    tin = sum(u.get("input_tokens", 0) for u in usage.usage_metadata.values())
    tout = sum(u.get("output_tokens", 0) for u in usage.usage_metadata.values())
    return {
        "id": task["id"], "category": task["category"], "design": design, "backend": BACKEND,
        "answer": answer, "error": err, "tools": log.tools,
        "tool_ok": set(log.tools) == set(task["expected_tools"]),
        "success": bool(answer) and score(task, answer),
        "secs": round(secs, 1), "tokens_in": tin, "tokens_out": tout,
        "usd": round((tin * PRICE[0] + tout * PRICE[1]) / 1e6, 5),
    }


def run(design: str, limit: int | None):
    tasks = [json.loads(l) for l in (HERE / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()][:limit]
    RAW.mkdir(exist_ok=True)
    for d in (["react", "plan"] if design == "both" else [design]):
        path = RAW / f"{BACKEND}-{d}.jsonl"
        done = {json.loads(l)["id"] for l in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
        agent = (graph_react if d == "react" else graph_plan).build(hitl=False)
        for t in tasks:
            if t["id"] in done:
                continue
            r = run_one(agent, d, t)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"{d} {t['id']} ok={r['success']} tools_ok={r['tool_ok']} {r['secs']}s", flush=True)


def report():
    rows = [json.loads(l) for p in sorted(RAW.glob("*.jsonl")) for l in p.read_text(encoding="utf-8").splitlines()]
    expected = {t["id"]: set(t["expected_tools"]) for t in map(json.loads, (HERE / "tasks.jsonl").read_text(encoding="utf-8").splitlines())}
    for r in rows:  # looser tool metric: every expected tool was used (extra calls allowed)
        r["tool_cover"] = expected[r["id"]] <= set(r["tools"])
    groups = defaultdict(list)
    for r in rows:
        groups[(r["backend"], r["design"])].append(r)
    pct = lambda xs: f"{100 * sum(xs) / len(xs):.0f}%"
    out = ["| backend | design | n | task success | tool-choice acc (exact) | tools covered | avg latency (s) | avg tokens | total cost (USD) |", "|---|---|---|---|---|---|---|---|---|"]
    cats = defaultdict(dict)
    for (b, d), rs in groups.items():
        out.append(f"| {b} | {d} | {len(rs)} | {pct([r['success'] for r in rs])} | {pct([r['tool_ok'] for r in rs])} | {pct([r['tool_cover'] for r in rs])} | "
                   f"{sum(r['secs'] for r in rs) / len(rs):.1f} | {sum(r['tokens_in'] + r['tokens_out'] for r in rs) / len(rs):.0f} | "
                   f"{sum(r['usd'] for r in rs):.3f} |")
        for c in sorted({r["category"] for r in rs}):
            sub = [r for r in rs if r["category"] == c]
            cats[c][f"{b}/{d}"] = f"{pct([r['success'] for r in sub])} ({len(sub)})"
    keys = sorted({k for v in cats.values() for k in v})
    out += ["", "Task success by category:", "", "| category | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    out += [f"| {c} | " + " | ".join(v.get(k, "-") for k in keys) + " |" for c, v in sorted(cats.items())]
    (HERE / "results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--design", choices=["react", "plan", "both"], default="both")
    r.add_argument("--limit", type=int)
    sub.add_parser("report")
    a = ap.parse_args()
    report() if a.cmd == "report" else run(a.design, a.limit)
