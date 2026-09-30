# Phase 0 — Bootstrap: repo, backend switch, retrieval core

Study note: what exists after this phase, why, and the concepts behind it.
Code: [llm.py](../src/agent/llm.py), [retrieval.py](../src/agent/retrieval.py).

## The problem it solves
Everything later (agents, evals, MCP, Lambda) needs two things to be swappable without touching agent code:
the **LLM/embedding provider** and the **vector index**. Local dev must be free and offline-capable (Ollama);
the deployed version must run on AWS (Bedrock). One env var decides: `LLM_BACKEND=ollama|bedrock`.

## What exists now
| What | Where | Why |
|---|---|---|
| New repo `agentic-rag-aws` | repo root | Fresh start; only the retrieval core is copied from `../LangChains` |
| Backend switch | `llm.py` (`get_llm`, `get_embeddings`) | The single place that knows about Ollama/Bedrock |
| FAISS index per backend | `index/<backend>/` | Embedding models differ (mpnet 768-d vs Titan 1024-d), so indexes are not interchangeable |
| Corpus | `data/*.pdf` (7 arXiv papers, Asymptotic Safety) | Copied from LangChains; ids listed in `data/SOURCES.md` |
| Ingest | `python -m agent.retrieval` | PyMuPDF -> RecursiveCharacterTextSplitter (512/64) -> FAISS. Result: **1465 chunks** locally |

## Decisions (and what was skipped)
- **FAISS file instead of Chroma.** Chroma needs a persistent dir with SQLite; a FAISS folder can be baked
  into a Lambda image and loaded in about 1 s. Ceiling: no metadata filtering, no incremental updates
  (rebuild the index). Upgrade path: OpenSearch Serverless / pgvector if the corpus grows.
- **Local embeddings = all-mpnet-base-v2** (the model the LangChains ablation picked), imported lazily so the
  Lambda image never pulls torch. **AWS embeddings = Titan Text Embeddings v2.**
- **Local LLM = `gemma4:12b`, not llama3.** `ollama show llama3` reports only the `completion` capability,
  i.e. no tool calling. gemma4 lists `tools`. Thinking is switched off (`reasoning=False`):
  on an 8 GB laptop GPU it turned a 4-minute query into 37 s.
- **No `uv`, no new venv.** The existing `torch_env` conda env already had torch/sentence-transformers;
  `requirements.txt` lists the rest (`langgraph`, `langchain-aws`, `faiss-cpu`, `mcp`, `ddgs`, ...).

## Gotchas
- FAISS pickles the docstore, so `FAISS.load_local(..., allow_dangerous_deserialization=True)` is required;
  it is safe only because we wrote the index ourselves (comment in code).
- The corpus is 7 papers, not the ~20 of the original plan: enough to measure agent behaviour, and the
  eval set (Phase 3) is built on it. Adding papers = drop PDFs in `data/`, rebuild.
