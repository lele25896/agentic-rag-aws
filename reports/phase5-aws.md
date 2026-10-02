# Phase 5 — AWS: Lambda + Bedrock + DynamoDB, in Terraform

Code: [infra/main.tf](../infra/main.tf), [Dockerfile](../Dockerfile), [scripts/deploy.sh](../scripts/deploy.sh),
[src/agent/handler.py](../src/agent/handler.py), [tests/test_handler.py](../tests/test_handler.py).

## Status
**Deployed and verified on 2026-10-02** (account eu-west-1, Function URL protected by `x-api-key`).
| Check | Result |
|---|---|
| `terraform apply` | 10 resources (+1 permission added after the first test), clean |
| Wrong/missing key | 401 from the handler |
| `/chat` plain question (react) | 200, "42", ~8-13 s (cold start ~4 s) |
| `/chat` retrieval question | 200, correct paper id, FAISS + Titan index baked into the image |
| `/chat` gated question | `needs_approval` with `{tool: extract_pdf, args}` |
| `/approve` (a different invocation) | 200, correct title + authors; paused state came back from DynamoDB |
| `/chat` plan design | 200, 6-10 s typical, one 40 s outlier (see below) |
| Cost of the whole session | well under USD 2 (Bedrock evals ~USD 1.4 incl. reruns, rest is free tier) |

## What the first live deploy broke (and the fixes)
1. **403 from AWS before the handler ran.** Since late 2025 a public (auth NONE) Function URL needs *two*
   resource policies: `lambda:InvokeFunctionUrl` **and** `lambda:InvokeFunction` with
   `lambda:InvokedViaFunctionUrl = true`. Terraform provider 5.x has no flag for the second one, so the
   provider constraint moved to `>= 6.0` (`invoked_via_function_url = true`). Found by testing the live URL.
2. **`invalid json` on a valid request.** Function URLs deliver the body base64-encoded
   (`isBase64Encoded: true`) unless the content type is JSON/text; `curl -d` sends form-encoded. Handler now
   decodes (`test_base64_body_is_decoded`).
3. **New image, old code.** Pushing `:latest` again changes nothing for Terraform (same tag), so Lambda kept
   running the old image. `deploy.sh` now calls `update-function-code` + `wait function-updated`.
4. **Sporadic ~60 s stalls** on Bedrock calls (botocore's default read timeout, then a successful retry; also
   one 64 s outlier in the eval). Client config is now `read_timeout=30, max_attempts=3`: a hung call retries
   after 30 s. Residual: an occasional 30-40 s request.

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
1. Bedrock: submit the Anthropic use-case form once; wait for account verification (it blocked both Titan and Haiku for a while); model access can take ~15 min to propagate.
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
