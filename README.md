# agentic-rag-aws

A LangGraph agent over a small corpus of research papers, with four tools, human-in-the-loop approval,
an MCP server, an eval harness comparing two agent designs, and a Terraform-defined AWS deployment
(Lambda + Bedrock + DynamoDB). `LLM_BACKEND=ollama|bedrock` switches between fully local and AWS.

## Status
| Piece | State |
|---|---|
| Agent (ReAct + plan-and-execute), tools, HITL | done, tested locally |
| MCP server | done, tested over stdio |
| Evals (30 tasks x 2 designs) | done on Ollama and Bedrock |
| AWS (Terraform, Docker, handler) | **deployed and tested on 2026-10-02** (eu-west-1: Lambda + Bedrock + DynamoDB), then torn down to avoid cost. Redeploy in ~3 min with `scripts/deploy.sh`. Recorded session: [docs/demo.md](docs/demo.md) |

## Architecture
```
question -> agent (LangGraph) -> tools: search_papers (FAISS) | extract_pdf | calc | web_search
              ^  design A: ReAct loop         gated tools pause for human approval (interrupt + checkpointer)
              |  design B: plan -> steps -> synthesize
same tools ---> MCP server (stdio)
AWS: Function URL -> Lambda (image) -> Bedrock + FAISS in image + DynamoDB checkpoints
```

## Eval results (30 tasks, temperature 0, one run each)
| backend | design | task success | tool-choice (exact) | expected tools covered | avg latency | avg tokens | cost / 30 tasks |
|---|---|---|---|---|---|---|---|
| Bedrock, Claude Haiku 4.5 (eu) | ReAct | 87% | 43% | 90% | 7.5 s | 12.4k | $0.49 |
| Bedrock, Claude Haiku 4.5 (eu) | Plan-and-execute | 90% | 43% | 100% | 15.9 s | 22.9k | $0.94 |
| Ollama, gemma4:12b (laptop GPU) | ReAct | 83% | 67% | 93% | 33 s | 3.9k | 0 |
| Ollama, gemma4:12b (laptop GPU) | Plan-and-execute | 80% | 30% | 100% | 77 s | 9.4k | 0 |

Quality is about equal (the 3-point gaps are 1 task); plan-and-execute costs about 2x the tokens, money and
latency.

Caveats: the judge for the retrieval tasks is the same model as the agent; n=30 and one run per cell, so
differences of 1-3 points are noise; the exact tool-choice metric counts harmless extra calls as errors (hence the
looser "covered" column). The first Bedrock run crashed on 13 of 60 tasks because model-supplied field names in
`extract_pdf` violate Bedrock's schema-key rule; names are now sanitised and only the crashed tasks were rerun.

## Run it locally
The corpus PDFs are not committed (ids and titles in `data/SOURCES.md`). Fetch them once:
```bash
for id in 1202.2274v1 1707.09298v5 2504.07877v1 2508.00807v2 2509.12469v2 2601.20820v2 2605.11805v1; do
  curl -L -o data/$id.pdf https://arxiv.org/pdf/$id; done
```
```bash
pip install -r requirements.txt            # torch env needed for local embeddings
export PYTHONPATH=src
python -m agent.retrieval                  # build index/ollama
python -m agent.cli "Which paper studies regular black holes?"            # design A, asks approval for gated tools
python -m agent.cli --design plan "..."                                    # design B
python -m agent.mcp_server                                                 # MCP over stdio
python evals/run.py run && python evals/run.py report
python -m pytest tests -q
```
Local model: `gemma4:12b` (needs tool calling; llama3 has none). Override with `OLLAMA_MODEL`.

## Deploy to AWS
The stack is currently **not running**; this is a recorded demo, see [docs/demo.md](docs/demo.md).
Needs `aws` (configured), `docker`, `terraform`, Bedrock access to Claude Haiku 4.5 and Titan Text Embeddings v2
in the chosen region (default `eu-west-1`; the Anthropic use-case form must be submitted once per account).
```bash
LLM_BACKEND=bedrock PYTHONPATH=src python -m agent.retrieval     # build index/bedrock (baked into the image)
export TF_VAR_alert_email=you@example.com                         # budget alarm: USD 10/month, alert at 80%
bash scripts/deploy.sh                                            # ECR -> image -> Lambda + Function URL + DynamoDB
terraform -chdir=infra output -raw api_key                        # send as header x-api-key
curl -X POST $URL/chat -H "x-api-key: $KEY" -d '{"question":"...","design":"react"}'
curl -X POST $URL/approve -H "x-api-key: $KEY" -d '{"thread_id":"...","approve":true}'
bash scripts/deploy.sh --destroy                                  # remove everything
```
`/chat` returns `done` or `needs_approval` (with the pending tool call); `/approve` resumes the paused run from
DynamoDB. Public Function URLs need two Lambda permissions (`InvokeFunctionUrl` and `InvokeFunction`), which is why
the Terraform AWS provider is pinned to `>= 6.0`.

## Layout
`src/agent/` (llm, retrieval, tools, graph_react, graph_plan, cli, mcp_server, handler) - `evals/` - `infra/` -
`tests/` - `docs/` (recorded demo) - `data/` (7 arXiv PDFs, ids in `data/SOURCES.md`).
