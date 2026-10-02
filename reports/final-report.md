# Final Report — agentic-rag-aws

**Project:** LangGraph agent over a small research-paper corpus, with human-in-the-loop approval, an MCP server,
a 30-task eval comparing two agent designs on two backends, and a Terraform-defined AWS deployment.
**Span:** 2026-09-30 → 2026-10-02
**Owner:** Gabriele Giacometti
**Status:** done and deployed (eu-west-1). Teardown is one command (`scripts/deploy.sh --destroy`).

---

## 1. Executive summary

A question goes to an agent that chooses between four tools (paper search, PDF field extraction, a safe
calculator, web search). Two of the tools pause the run for a human yes/no. The same tools are exposed over MCP.
The agent runs fully local (Ollama) or on AWS (Lambda + Bedrock + DynamoDB), switched by one env var.

| | value |
|---|---|
| code | ~800 lines in total (src 380, evals 130, tests 100, Terraform/Docker/deploy 190) |
| tests | 7 passing: calc safety, path traversal, field-name sanitising, MCP over stdio, handler auth/base64 |
| eval | 30 tasks x 2 designs x 2 backends (120 task runs), all scored |
| AWS | 10 Terraform resources, deployed and verified over HTTP, including pause/approve across invocations |
| cost | about USD 1.5 for the whole project (Bedrock evals + a few hundred test calls); idle cost is pennies |

**Headline result:** on Claude Haiku 4.5, plan-and-execute and ReAct reach the same quality (90% vs 87%,
one task apart), but plan-and-execute costs twice as much and takes twice as long. The extra structure bought
nothing measurable on this task set.

---

## 2. Architecture

```
question -> agent (LangGraph) -> search_papers (FAISS) | extract_pdf | calc | web_search
   design A: prebuilt ReAct loop            gated tools: interrupt() + checkpointer
   design B: planner -> step* -> synthesizer
same four functions -> MCP server (stdio)
AWS: Function URL (x-api-key) -> Lambda image -> Bedrock (Haiku 4.5, Titan v2) + FAISS in image + DynamoDB checkpoints
```

Key decisions (each has a `ponytail:` note or phase report behind it):
- **One tool layer, three front-ends** (agents, MCP, HTTP). Gating lives in the agent layer, not in the tools.
- **FAISS file baked into the Lambda image** instead of a vector database: no server, ~1 s load. Ceiling: full rebuild on change.
- **Lambda, not Fargate**: scale to zero, no cluster. **DynamoDB checkpointer** because `/approve` can land on another instance than `/chat`.
- **Local model must support tool calling**: `llama3` does not; `gemma4:12b` does (thinking off, otherwise minutes per query on an 8 GB GPU).
- **Strict scope**: no UI, no FastAPI, no Knowledge Bases, no second cloud.

---

## 3. Results

| backend | design | task success | tool-choice (exact) | expected tools covered | avg latency | avg tokens | cost / 30 tasks |
|---|---|---|---|---|---|---|---|
| Bedrock, Haiku 4.5 (eu) | ReAct | 87% | 43% | 90% | 7.5 s | 12.4k | $0.49 |
| Bedrock, Haiku 4.5 (eu) | Plan-and-execute | 90% | 43% | 100% | 15.9 s | 22.9k | $0.94 |
| Ollama, gemma4:12b | ReAct | 83% | 67% | 93% | 33 s | 3.9k | 0 |
| Ollama, gemma4:12b | Plan-and-execute | 80% | 30% | 100% | 77 s | 9.4k | 0 |

By category the picture is stable: calc and web ~100%, mixed (corpus fact + calculation) 80-100%,
retrieval 67% locally and 92% on Haiku, extraction 60-80%. Retrieval failures overlap across designs
(same questions fail for both), which points at chunking/top-k, not at the agent loop.

---

## 4. What the real cloud broke (the useful part)

Everything below passed locally and failed only against Bedrock or Lambda. None showed up in unit tests.

1. **Bedrock rejected 13 of 60 runs** with a `ValidationException`: `extract_pdf` turns *model-supplied* field names
   ("main contribution") into JSON-schema keys, and Bedrock only accepts `[a-zA-Z0-9_.-]`. Ollama accepted them silently.
   Fix at the trust boundary + a test. Lesson: a provider swap is a test run, not a config change.
2. **403 before the handler ran.** A public Function URL now needs two resource policies
   (`InvokeFunctionUrl` and `InvokeFunction` with `InvokedViaFunctionUrl`). Terraform provider 5.x cannot express the
   second one; moved to provider 6.x.
3. **`invalid json` on valid requests.** Function URLs base64-encode the body unless the content type is JSON.
4. **New image, old code.** Re-pushing `:latest` is invisible to Terraform; the deploy script now calls
   `update-function-code`.
5. **Sporadic 60 s stalls** on Bedrock calls (botocore's read timeout, then a successful retry). Client now uses
   `read_timeout=30, max_attempts=3`; residual outliers are 30-40 s.
6. **Account friction**: new-account verification and the Anthropic use-case form each blocked a model for a while;
   access propagated ~15 min after the console said it was done.

---

## 5. Limits and honest caveats

- **The judge is the same model as the agent** (retrieval tasks): self-preference bias is possible.
- **n = 30, one run per cell**, temperature 0. A 1-3 point gap is one task, not a result. No confidence intervals.
- **Tool-choice is strict set equality**, so harmless extra calls count as errors; the "covered" column is the looser view.
- **Tiny corpus** (7 papers on one topic). Retrieval quality on a broader corpus is untested.
- **Auth is one shared API key** on a public URL: fine for a demo, not for users. Upgrade: IAM auth or API Gateway + Cognito.
- **No reranking, no hybrid search, no streaming.** `extract_pdf` reads the first 4 pages only.
- Bedrock IAM is `Resource: "*"` (marked in code); tighten if it outlives the demo.

---

## 6. Reproduce

```bash
pip install -r requirements.txt && export PYTHONPATH=src
# fetch the 7 papers (see README), then:
python -m agent.retrieval                       # index (LLM_BACKEND=ollama|bedrock)
python -m agent.cli "your question"             # asks approval for gated tools
python evals/run.py run && python evals/run.py report
python -m pytest tests -q
bash scripts/deploy.sh                          # needs aws, docker, terraform, Bedrock access
bash scripts/deploy.sh --destroy
```

## 7. Follow-ups (not done, by scope)
- A reranker or hybrid retrieval, then re-run the retrieval slice (the weakest category).
- Repeat each cell 3-5 times and add intervals; use a different model as judge.
- Replace the shared API key with IAM/Cognito; tighten Bedrock IAM to the inference-profile ARNs.
- Add papers (drop PDFs in `data/`, rebuild the index) to test beyond 7 documents.
