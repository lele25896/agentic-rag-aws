#!/usr/bin/env bash
# Deploy: bash scripts/deploy.sh [--destroy].  Needs aws/docker/terraform + AWS creds + Bedrock model access.
set -euo pipefail
cd "$(dirname "$0")/.."
TF="terraform -chdir=infra"
: "${TF_VAR_alert_email:?export TF_VAR_alert_email=you@example.com (budget alerts)}"
for c in aws docker terraform; do command -v "$c" >/dev/null || { echo "missing: $c"; exit 1; }; done

if [ "${1:-}" = "--destroy" ]; then $TF destroy -auto-approve; exit 0; fi

[ -f index/bedrock/index.faiss ] || { echo "run first: LLM_BACKEND=bedrock PYTHONPATH=src python -m agent.retrieval"; exit 1; }

$TF init -input=false
$TF apply -auto-approve -target=aws_ecr_repository.repo   # repo must exist before the push
REPO=$($TF output -raw ecr_repository_url)
REGION=$(aws configure get region || echo eu-west-1)
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${REPO%%/*}"
docker build --provenance=false -t "$REPO:latest" .   # Lambda rejects OCI attestation manifests
docker push "$REPO:latest"
$TF apply -auto-approve
# same :latest tag => terraform sees no diff, so point Lambda at the freshly pushed image explicitly
aws lambda update-function-code --region "$REGION" --function-name agentic-rag --image-uri "$REPO:latest" >/dev/null
aws lambda wait function-updated --region "$REGION" --function-name agentic-rag
echo "URL: $($TF output -raw function_url)"
echo "API key: terraform -chdir=infra output -raw api_key"
