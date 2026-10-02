# Phase 3 — Evals: 30 tasks, two agent designs

Code: [evals/run.py](../evals/run.py), [evals/tasks.jsonl](../evals/tasks.jsonl), results in [evals/results.md](../evals/results.md), raw per-task rows in `evals/raw/`.

## The problem it solves
"It seems to work" is not a portfolio claim. The eval turns agent behaviour into numbers and compares
design A (ReAct) with design B (plan-and-execute) on identical tasks, tools and model.

## The task set (30)
| category | n | how it is scored |
|---|---|---|
| retrieval | 12 | LLM judge vs the hand-curated ground truth from `../LangChains/test_set.json` |
| calc | 5 | any number in the answer within 1% of the exact value |
| extract | 5 | all expected substrings present (verified to exist in the first 4 pages) |
| web | 3 | expected substrings (2024/2025 Nobel Physics, Euro 2024) |
| mixed | 5 | corpus fact + calc, or corpus + web |

Metrics per task: **success**, **tool-choice** (used tool set == expected tool set, strict),
latency, input/output tokens, cost (USD per 1M tokens: Bedrock 1/5; Ollama 0). Callbacks capture tool names
and usage from nested calls, so design B's planner/executor/synthesizer are all counted.
A crashed task is recorded as a failure, not an aborted run. HITL is off (auto-approve) so human wait time
does not pollute latency.

## Results (Ollama, gemma4:12b, temperature 0, one run)
| design | n | task success | tool-choice acc | avg latency | avg tokens |
|---|---|---|---|---|---|
| react | 30 | **83%** (25) | **67%** (20) | **33 s** | **3.9k** |
| plan | 30 | 80% (24) | 30% (9) | 77 s | 9.4k |

By category (success): calc react 100% / plan 80%; extract 80/80; mixed 100/100; retrieval 67/67; web 100/100.

## Results (Bedrock, Claude Haiku 4.5 via the `eu.` inference profile, eu-west-1)
| design | n | task success | tool-choice (exact) | expected tools covered | avg latency | avg tokens | cost (30 tasks) |
|---|---|---|---|---|---|---|---|
| react | 30 | **87%** (26) | 43% | 90% | **7.5 s** | **12.4k** | **$0.49** |
| plan | 30 | **90%** (27) | 43% | 100% | 15.9 s | 22.9k | $0.94 |

By category (success): calc 100/100; extract 60/60; mixed react 80% / plan 100%; retrieval 92/92; web 100/100.
Cost uses USD 1.10 in / 5.50 out per 1M tokens (EU regional profile, +10% over global; Bedrock pricing page,
checked 2026-10-02). Token counts include Haiku's tool-use overhead, which is why they are 3x the Ollama counts.

**What the first Bedrock run taught us:** 13 of 60 runs crashed with a `ValidationException`. `extract_pdf` turns
model-supplied field names ("main contribution") into JSON-schema property keys, and Bedrock only accepts
`[a-zA-Z0-9_.-]`. Ollama tolerated it silently. Fix: sanitize names at that trust boundary and return an error
string instead of raising (`test_extract_pdf_sanitizes_field_names`). Only the crashed tasks were rerun
(the runner resumes and skips finished ids). Lesson: a provider swap is a test, not a config change.

## Reading the numbers (Ollama run; Bedrock tells the same story)
- **ReAct wins on cost and speed, ties on quality:** about 2.3x faster and 2.4x fewer tokens for the same
  success rate (83% vs 80% is 1 task, well inside noise at n=30).
- **Plan-and-execute picked the expected tool set far less often (30% vs 67%).** Success stayed high, so the
  extra calls were mostly redundant, not wrong. Strict set-equality punishes any extra tool; a looser
  "expected is a subset of used" metric would show a smaller gap. Both are worth reporting.
- **Both designs are weakest on retrieval (67%).** Each design misses 4 of 12
  (react: t02, t03, t05, t10; plan: t03, t05, t09, t11), and t03 and t05 fail for both. Common failures
  point at the retrieval layer (chunking/top-k/reranking) rather than the agent design.
- Calc and mixed tasks are at or near 100%: the tools and the tool-calling path work.

## Caveats (read before quoting the table)
- **The judge is the same model as the agent** (gemma4:12b): self-preference bias is possible.
- n=30, one run, so differences of 1-2 tasks are noise. No confidence intervals.
- Tool-choice is strict set equality; several "wrong" tool sets are harmless extra calls.
- Bedrock numbers are also a single run; the Haiku judge is the same model as the agent there too.

## Reproduce
```bash
python evals/run.py run --design both     # resumable; ~70 min on a laptop GPU
python evals/run.py report                # regenerates evals/results.md
```
