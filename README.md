# agentic-rag-aws

A LangGraph agent over a small corpus of research papers, with four tools, human-in-the-loop approval,
an MCP server, an eval harness comparing two agent designs, and a Terraform-defined AWS deployment
(Lambda + Bedrock + DynamoDB). `LLM_BACKEND=ollama|bedrock` switches between fully local and AWS.

## Status
| Piece | State |
|---|---|
| Agent (ReAct + plan-and-execute), tools, HITL | done, tested locally |
| MCP server | done, tested over stdio |
| Evals (30 tasks x 2 designs) | done on Ollama; Bedrock run pending |
| AWS (Terraform, Docker, handler) | written, `terraform validate` passes, **not deployed** |

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
latency. Caveats (same-model judge, n=30, strict tool metric) in [reports/phase3-evals.md](reports/phase3-evals.md).

## Run it locally
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
See [reports/phase5-aws.md](reports/phase5-aws.md). `bash scripts/deploy.sh` / `--destroy`.

## Layout
`src/agent/` (llm, retrieval, tools, graph_react, graph_plan, cli, mcp_server, handler) - `evals/` - `infra/` -
`tests/` - `reports/` (one study note per phase) - `data/` (7 arXiv PDFs, ids in `data/SOURCES.md`).
