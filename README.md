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

## Eval results (Ollama gemma4:12b, 30 tasks, temperature 0, one run)
| design | task success | tool-choice acc | avg latency | avg tokens |
|---|---|---|---|---|
| ReAct | 83% | 67% | 33 s | 3.9k |
| Plan-and-execute | 80% | 30% | 77 s | 9.4k |

ReAct matches plan-and-execute on quality at about 2.3x lower latency and 2.4x fewer tokens.
Caveats (same-model judge, n=30, strict tool metric) in [reports/phase3-evals.md](reports/phase3-evals.md).

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
