"""Picks the LLM backend at runtime based on which API key is configured.

Priority: Azure OpenAI (prod) -> Groq -> Claude -> local OpenAI-compatible
-> offline extractive (grounded answers, no key needed).

Both clients share the same interface (complete / analyze_document /
answer_question / get_auto_suggestions / .online / .last_error), so callers
don't care which one they get.
"""
from __future__ import annotations

import os


def get_llm_client():
    """Return the best available LLM client and a short backend label.

    Priority: Azure OpenAI -> Groq -> Claude -> local OpenAI-compatible
    (Ollama/vLLM via LLM_BASE_URL) -> offline extractive (no key needed).
    """
    groq_key = (os.getenv("GROQ_API_KEY") or "").strip()
    claude_key = (os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    local_url = (os.getenv("LLM_BASE_URL") or "").strip()
    azure_ep = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip()
    azure_key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()

    # Azure OpenAI is the production connector (highest priority when configured).
    if azure_ep and azure_key:
        from src.agents.azure_openai_llm import AzureOpenAILLMClient
        client = AzureOpenAILLMClient()
        if client.online:
            client.provider = "azure_openai"
            return client, "azure_openai"

    if groq_key:
        from src.agents.groq_llm import GroqLLMClient
        c = GroqLLMClient(api_key=groq_key); c.provider = "groq"; return c, "groq"

    if claude_key:
        from src.agents.claude_llm import ClaudeLLMClient
        client = ClaudeLLMClient(api_key=claude_key)
        if client.online:
            client.provider = "claude"; return client, "claude"

    if local_url:
        # Ollama / vLLM / any OpenAI-compatible server. Ollama ignores the key.
        from src.agents.groq_llm import GroqLLMClient
        client = GroqLLMClient(
            api_key=(os.getenv("LLM_API_KEY") or "ollama"),
            model=os.getenv("LLM_MODEL", "llama3.1:8b"),
            base_url=local_url,
        )
        if client.online:
            client.provider = "local"; return client, "local"

    from src.agents.claude_llm import ClaudeLLMClient
    c = ClaudeLLMClient(api_key=None); c.provider = "offline"; return c, "offline"
