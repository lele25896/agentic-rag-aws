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
