# Live demo transcript (2026-10-02)

Real output from the deployed stack (AWS eu-west-1: Lambda container + Function URL, Bedrock Claude Haiku 4.5,
DynamoDB checkpoints). `$URL` is the Function URL and `$KEY` the API key; both are omitted here. The stack has since
been torn down with `scripts/deploy.sh --destroy`; redeploying takes about 3 minutes.

Timings are wall-clock from a laptop in Italy, including one Lambda cold start (~4 s) for the first request of a session.

## 1. No API key -> rejected by the handler (1.8 s)
```bash
curl -X POST $URL/chat -d '{"question":"hi"}'
```
```
HTTP 401  {"error": "unauthorized"}
```

## 2. Retrieval question: search_papers over the FAISS index baked into the image (8.8 s)
```bash
curl -X POST $URL/chat -H "x-api-key: $KEY" \
  -d '{"question":"Which paper studies regular black holes? Cite the paper id.","design":"react"}'
```
```
HTTP 200  {"status": "done", "thread_id": "react:fbdafef8...", "answer": "The paper that studies regular black holes is
**2509.12469v2**. It's titled \"Regular Black Holes from Proper-Time flow in Quantum Gravity and their Quasinormal
modes, Shadow and Hawking radiation\" by Bonanno, Konoplya, Oglialoro, and Spina. ..."}
```

## 3. Gated tool: the run pauses, a second request approves it (1.5 s + 7.9 s)
`extract_pdf` is an approval-gated tool. The first call returns the pending tool call instead of an answer; the graph
state is saved in DynamoDB.
```bash
curl -X POST $URL/chat -H "x-api-key: $KEY" \
  -d '{"question":"Extract the title and authors from paper 2504.07877v1.","design":"react"}'
```
```
HTTP 200  {"status": "needs_approval", "thread_id": "react:f464dd3d...",
           "pending": {"tool": "extract_pdf", "args": {"source": "2504.07877v1", "fields": ["title", "authors"]}}}
```
The approval is a separate Lambda invocation (possibly another instance); it resumes from DynamoDB:
```bash
curl -X POST $URL/approve -H "x-api-key: $KEY" -d '{"thread_id":"react:f464dd3d...","approve":true}'
```
```
HTTP 200  {"status": "done", "thread_id": "react:f464dd3d...", "answer": "**Title:** Gauge and parametrization
dependence of Quantum Einstein Gravity within the Proper Time flow\n\n**Authors:** Alfio Bonanno, Giovanni Oglialoro,
Dario Zappalà"}
```

## 4. Denying the tool call (about 7 s)
Same pause, then `"approve": false`. The tool is skipped and the model says so instead of inventing an answer:
```
HTTP 200  {"status": "done", "answer": "I apologize, but I'm unable to extract the main contribution from paper
2605.11805v1 at this time. The extraction was denied. ..."}
```
Note: the first attempt of this step in the recording session returned no response (curl HTTP code 000 after ~22 s,
a client-side connection failure; the Lambda logs show no error). A retry on a fresh thread worked as shown.

## 5. Plan-and-execute design (6.4 s)
```bash
curl -X POST $URL/chat -H "x-api-key: $KEY" -d '{"question":"Compute 17*23 then add 9.","design":"plan"}'
```
```
HTTP 200  {"status": "done", "thread_id": "plan:440dd1b2...", "answer": "# Final Answer\n\n**17 × 23 + 9 = 400**
\n\n**Calculation:**\n- 17 × 23 = 391\n- 391 + 9 = 400"}
```
Earlier in the same session this request sometimes took 40-70 s because of occasional hung Bedrock calls; the client
now uses `read_timeout=30` with retries (see `reports/phase5-aws.md`).
