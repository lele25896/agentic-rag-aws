# Phase 5 — AWS: Lambda + Bedrock + DynamoDB, in Terraform

Code: [infra/main.tf](../infra/main.tf), [Dockerfile](../Dockerfile), [scripts/deploy.sh](../scripts/deploy.sh),
[src/agent/handler.py](../src/agent/handler.py), [tests/test_handler.py](../tests/test_handler.py).

## Status (honest)
| Piece | State |
|---|---|
| `handler.py` auth + routing + validation | **tested locally** (`test_handler.py`) |
| Terraform | **`terraform validate` passes**, `fmt` clean. Never applied: no AWS credentials on this machine |
| `deploy.sh` | `bash -n` passes. Never run (no `aws` CLI here; needs docker + creds) |
| Docker image | not built |
| `LLM_BACKEND=bedrock` path (`ChatBedrockConverse`, Titan embeddings, `DynamoDBSaver`) | code written, **not exercised** |
| End-to-end HITL over HTTP | logic covered by the local CLI smoke (Phase 2); HTTP + DynamoDB leg untested |

So "deployed" in the project's *Done when* is **still open**; everything needed to close it is in the repo.

## Architecture
```
client --HTTPS (x-api-key)--> Lambda Function URL --> Lambda (container image, 2 GB, 120 s)
                                                        |-- Bedrock Converse (Claude Haiku 4.5) + Titan embeddings
                                                        |-- FAISS index + PDFs baked into the image
                                                        `-- DynamoDB (LangGraph checkpoints, TTL 24 h)
```
- `POST /chat {question, design}` -> `done` or `needs_approval {thread_id, pending{tool,args}}`.
- `POST /approve {thread_id, approve}` -> resumes the paused graph. `thread_id` is `"<design>:<uuid>"`, so the
  handler knows which graph to resume without extra state.

## Decisions (and what was skipped)
- **Lambda, not Fargate.** Scale-to-zero, no cluster, no ALB. Ceiling: 15 min max, cold start of a few seconds
  (FAISS load + langchain imports). The agent answers in well under the 120 s timeout on Haiku.
- **Function URL with auth NONE + shared `x-api-key`** (`hmac.compare_digest`) instead of API Gateway or
  SigV4: one fewer service, `curl`-able. Ceiling: single shared secret, no per-user auth, no rate limit.
  Upgrade: IAM auth or API Gateway + Cognito.
- **DynamoDB checkpointer** (`langgraph-checkpoint-aws`): table schema `PK`/`SK` strings + `ttl` number,
  on-demand billing. Required because `/approve` may hit another Lambda instance than `/chat`.
- **Index baked into the image**, built locally with `LLM_BACKEND=bedrock python -m agent.retrieval`
  (needs Bedrock creds once). Upgrade path: S3 + load at cold start if the corpus changes often.
- **Bedrock IAM is `Resource: "*"`** with a `ponytail:` comment: least-privilege ARNs for inference profiles
  are fiddly; tighten if the project outlives the demo.
- **Cost guard:** monthly budget of USD 10 with an 80% e-mail alert; log retention 14 days;
  `scripts/deploy.sh --destroy` removes everything (`force_delete` on the ECR repo).

## How to deploy (needs an AWS account)
1. Enable model access in the Bedrock console for Claude Haiku 4.5 and Titan Text Embeddings v2 (eu-west-1).
2. `aws configure` (or SSO), `export TF_VAR_alert_email=you@example.com`.
3. `LLM_BACKEND=bedrock PYTHONPATH=src python -m agent.retrieval` -> `index/bedrock/`.
4. `bash scripts/deploy.sh` -> prints the Function URL; key: `terraform -chdir=infra output -raw api_key`.
5. `curl -X POST $URL/chat -H "x-api-key: $KEY" -d '{"question":"...","design":"react"}'`.
6. Run the evals on Bedrock (`LLM_BACKEND=bedrock python evals/run.py run`) for the cost column.
7. Afterwards: `bash scripts/deploy.sh --destroy`.

## Known risks
- Image build for Lambda needs `--provenance=false` (handled in the script) or Lambda rejects the manifest.
- The first `apply` needs the ECR repo to exist before the image push, hence the two-step `-target` apply.
- Bedrock cross-region inference profile ids (`eu.anthropic...`) must match the region.
