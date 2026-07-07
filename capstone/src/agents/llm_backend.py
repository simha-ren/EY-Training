"""Picks the LLM backend at runtime.

Callers may pass a preferred provider ("claude" or "groq" — chosen by the user in
the UI sidebar). Failover order is: preferred -> the other primary -> Azure OpenAI
(if configured) -> local OpenAI-compatible (LLM_BASE_URL) -> offline extractive.
So "selected -> other provider -> offline" holds, and the app always answers.

All clients share the same interface (complete / analyze_document /
answer_question / get_auto_suggestions / .online / .last_error), so callers don't
care which one they get.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple


def _build(provider: str):
    """Build a client for one provider. Returns (client, label) or (None, None)
    if that provider isn't configured / can't come online."""
    p = (provider or "").lower()
    try:
        if p == "groq":
            key = (os.getenv("GROQ_API_KEY") or "").strip()
            if key:
                from src.agents.groq_llm import GroqLLMClient
                c = GroqLLMClient(api_key=key)
                if c.online:
                    c.provider = "groq"; return c, "groq"
        elif p == "claude":
            key = (os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
            if key:
                from src.agents.claude_llm import ClaudeLLMClient
                c = ClaudeLLMClient(api_key=key)
                if c.online:
                    c.provider = "claude"; return c, "claude"
        elif p == "azure_openai":
            ep = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip()
            key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
            if ep and key:
                from src.agents.azure_openai_llm import AzureOpenAILLMClient
                c = AzureOpenAILLMClient()
                if c.online:
                    c.provider = "azure_openai"; return c, "azure_openai"
        elif p == "local":
            url = (os.getenv("LLM_BASE_URL") or "").strip()
            if url:
                from src.agents.groq_llm import GroqLLMClient
                c = GroqLLMClient(api_key=(os.getenv("LLM_API_KEY") or "ollama"),
                                  model=os.getenv("LLM_MODEL", "llama3.1:8b"), base_url=url)
                if c.online:
                    c.provider = "local"; return c, "local"
    except Exception:
        pass
    return None, None


def get_llm_client(provider: Optional[str] = None) -> Tuple[object, str]:
    """Return (client, backend_label).

    ``provider`` is the user's choice ("claude"/"groq"); when omitted the default
    preference is Claude. Falls over to the other provider, then Azure/local,
    then offline extractive (which always works, no key needed).
    """
    order = []
    if provider:
        order.append(provider.lower())
    # Default preference is Claude, then Groq — then the rest.
    for p in ["claude", "groq", "azure_openai", "local"]:
        if p not in order:
            order.append(p)

    for p in order:
        client, label = _build(p)
        if client is not None:
            return client, label

    # Nothing configured/reachable -> offline extractive (grounded, no key needed).
    from src.agents.claude_llm import ClaudeLLMClient
    c = ClaudeLLMClient(api_key=None)
    c.provider = "offline"
    return c, "offline"
