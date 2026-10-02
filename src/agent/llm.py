"""One switch for the whole project: LLM_BACKEND=ollama (local) | bedrock (AWS)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
BACKEND = os.environ.get("LLM_BACKEND", "ollama")
# separate FAISS index per backend: embedding dims/models differ
INDEX_DIR = Path(os.environ.get("INDEX_DIR", ROOT / "index")) / BACKEND

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:12b")  # llama3 has no tool calling
BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL", "eu.anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_EMBED = os.environ.get("BEDROCK_EMBED", "amazon.titan-embed-text-v2:0")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")


def get_llm():
    if BACKEND == "bedrock":
        from botocore.config import Config
        from langchain_aws import ChatBedrockConverse

        # Bedrock calls occasionally hang until botocore's 60 s read timeout; fail fast and retry instead
        cfg = Config(read_timeout=30, retries={"max_attempts": 3, "mode": "standard"})
        return ChatBedrockConverse(model=BEDROCK_MODEL, region_name=AWS_REGION, temperature=0, config=cfg)
    from langchain_ollama import ChatOllama

    # thinking off: 12B on an 8GB laptop GPU takes minutes per query otherwise
    return ChatOllama(model=OLLAMA_MODEL, temperature=0, reasoning=False)


def get_embeddings():
    if BACKEND == "bedrock":
        from langchain_aws import BedrockEmbeddings

        return BedrockEmbeddings(model_id=BEDROCK_EMBED, region_name=AWS_REGION)
    # lazy import: torch stays out of the Lambda image
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name="all-mpnet-base-v2", encode_kwargs={"normalize_embeddings": True}
    )
