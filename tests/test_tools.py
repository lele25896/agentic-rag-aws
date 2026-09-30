"""Fast checks, no LLM/network: python -m pytest tests -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agent.tools import calc, extract_pdf  # noqa: E402


def test_calc_ok():
    assert calc.invoke({"expression": "0.35 * 1200 / 7"}) == "60.0"
    assert calc.invoke({"expression": "sqrt(16) + 2**3"}) == "12.0"


def test_calc_rejects_code_and_bombs():
    assert calc.invoke({"expression": "__import__('os').system('echo hi')"}).startswith("error")
    assert calc.invoke({"expression": "9**9**9"}).startswith("error")
    assert calc.invoke({"expression": "open('x')"}).startswith("error")


def test_extract_pdf_blocks_path_traversal():
    assert extract_pdf.invoke({"source": "../../etc/passwd", "fields": ["a"]}).startswith("error")
