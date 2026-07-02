"""LLM abstraction layer.

Maps to the doc's 'Azure OpenAI (GPT-4o)' but is provider-agnostic:
- If an API key is configured, calls an OpenAI-compatible / Azure OpenAI endpoint.
- If no key is set, runs in OFFLINE mode and returns None so callers fall back
  to a deterministic extractive composer. This keeps the whole app runnable
  with zero credentials for the capstone demo.
"""
from __future__ import annotations

from typing import List, Optional


class LLMClient:
    def __init__(self, settings: dict):
        self.settings = settings or {}
        self.provider = self.settings.get("provider", "openai")
        self.api_key = self.settings.get("api_key", "")
        self.model = self.settings.get("model", "gpt-4o-mini")
        self._client = None
        self.online = bool(self.api_key)
        if self.online:
            try:
                self._init_client()
            except Exception as exc:  # pragma: no cover - depends on env
                self.online = False
                self._init_error = str(exc)

    def _init_client(self):
        if self.provider == "azure":
            from openai import AzureOpenAI

            self._client = AzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.settings.get("azure_endpoint", ""),
                api_version=self.settings.get("azure_api_version", "2024-06-01"),
            )
        else:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)

    def complete(self, system: str, user: str, temperature: float = 0.2) -> Optional[str]:
        """Return model text, or None when offline / on error."""
        if not self.online or self._client is None:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return resp.choices[0].message.content
        except Exception:
            return None

    def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Optional embeddings (used to upgrade retrieval). None when offline."""
        if not self.online or self._client is None:
            return None
        try:
            model = "text-embedding-3-small"
            resp = self._client.embeddings.create(model=model, input=texts)
            return [d.embedding for d in resp.data]
        except Exception:
            return None
