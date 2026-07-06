"""Azure OpenAI LLM connector.

Azure OpenAI exposes the same Chat Completions API as OpenAI, so this reuses the
GroqLLMClient method bodies (complete / chat / analyze_document / answer_question /
get_auto_suggestions / validate_completeness) and only swaps the transport to the
``AzureOpenAI`` client. The "model" is the Azure *deployment* name.

Enable in production by setting:
    AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
    AZURE_OPENAI_API_KEY=<key>
    AZURE_OPENAI_DEPLOYMENT=<deployment-name>        # e.g. gpt-4o-mini
    AZURE_OPENAI_API_VERSION=2024-06-01              # optional
The Bicep template (infra/deploy/azure/main.bicep) provisions the resource + a
deployment and injects the endpoint/deployment as app settings.
"""
from __future__ import annotations

import os
from typing import Optional

from .groq_llm import GroqLLMClient


class AzureOpenAILLMClient(GroqLLMClient):
    """OpenAI-compatible client pointed at an Azure OpenAI deployment."""

    def __init__(self, api_key: Optional[str] = None, deployment: Optional[str] = None,
                 endpoint: Optional[str] = None, api_version: Optional[str] = None):
        # Intentionally do NOT call super().__init__ (it builds a Groq client).
        self.api_key = (api_key or os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
        self.endpoint = (endpoint or os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip()
        self.deployment = (deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")
                           or "gpt-4o-mini").strip()
        self.api_version = (api_version or os.getenv("AZURE_OPENAI_API_VERSION")
                            or "2024-06-01").strip()
        # For the inherited methods, self.model is passed as the OpenAI "model" arg,
        # which for Azure must be the deployment name.
        self.model = self.deployment
        self.base_url = self.endpoint
        self.provider = "azure_openai"
        self.last_error: Optional[str] = None
        self.client = None
        self.online = bool(self.api_key and self.endpoint)
        if self.online:
            try:
                from openai import AzureOpenAI
                self.client = AzureOpenAI(
                    api_key=self.api_key,
                    azure_endpoint=self.endpoint,
                    api_version=self.api_version,
                )
            except Exception as exc:  # pragma: no cover - depends on env
                self.online = False
                self.last_error = str(exc)
        self.conversation_history = []
