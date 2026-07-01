import ast
from pathlib import Path


def test_parse_safety_guardrails():
    p = Path("safety_guardrails.py")
    assert p.exists(), "safety_guardrails.py must exist"
    src = p.read_text(encoding="utf-8")
    # Parse the file to ensure there are no syntax errors without executing it
    ast.parse(src)
