"""Offline-behaviour tests for the LLM client.

These are hermetic: monkeypatch removes any ambient API keys so the result is
deterministic whether or not the host has CLAUDE_API_KEY / ANTHROPIC_API_KEY set.
"""
import pytest
from core.claude_llm import ClaudeLLMClient

CTX = "The subsidy is INR 5000 per hectare. MSP is INR 3846 per quintal."


@pytest.fixture
def offline_env(monkeypatch):
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return ClaudeLLMClient(api_key=None)


def test_offline_client_is_offline(offline_env):
    assert offline_env.online is False

def test_answer_question_always_answers(offline_env):
    r = offline_env.answer_question(CTX, "what is the subsidy?")
    assert r["answer"] and r["mode"] == "offline"

def test_vague_question_asks_clarification(offline_env):
    r = offline_env.answer_question(CTX, "?")
    assert r["needs_clarification"] is True

def test_offline_suggestions_nonempty(offline_env):
    assert len(offline_env.get_auto_suggestions(CTX)) >= 1
