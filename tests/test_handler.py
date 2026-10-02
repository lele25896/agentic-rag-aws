"""Auth + routing only, no LLM: python -m pytest tests/test_handler.py -q"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ["API_KEY"] = "secret"
from agent.handler import handler  # noqa: E402


def call(path, body, key="secret"):
    r = handler({"rawPath": path, "headers": {"x-api-key": key} if key else {}, "body": json.dumps(body)})
    return r["statusCode"]


def test_auth_and_validation():
    assert call("/chat", {"question": "hi"}, key=None) == 401
    assert call("/chat", {"question": "hi"}, key="wrong") == 401
    assert call("/nope", {}) == 404
    assert call("/chat", {"design": "react"}) == 400
    assert call("/chat", {"question": "hi", "design": "evil"}) == 400
    assert call("/approve", {"thread_id": "x:1", "approve": True}) == 400


def test_base64_body_is_decoded():
    import base64

    body = base64.b64encode(json.dumps({"design": "evil", "question": "x"}).encode()).decode()
    r = handler({"rawPath": "/chat", "headers": {"x-api-key": "secret"}, "body": body, "isBase64Encoded": True})
    assert r["statusCode"] == 400 and "design" in r["body"]  # parsed fine, rejected by validation (not "invalid json")
