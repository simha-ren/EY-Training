"""Orchestrator (doc Section 3: the request-time control loop).

One entry point, ask(), runs the five-agent flow:
  route (Router) -> guardrail refuse check -> gap detect (clarification loop)
  -> retrieve (Retrieval) -> compose (Action/Generation) -> suggest.
Returns a single Turn object the UI renders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.common import guardrails
from src.agents import suggest
from src.common.config import DomainConfig, llm_settings, load_domains
from src.agents.generation import Answer, compose
from src.retrieval.ingestion import Chunk, ingest_upload, load_seed_corpus
from src.agents.llm import LLMClient
from src.orchestrator.router import DomainRouter, RouteResult
from src.retrieval.store import KnowledgeStore


@dataclass
class Turn:
    query: str
    route: RouteResult
    status: str                          # answer | clarify | refuse | ask_domain
    domain: Optional[str] = None
    message: str = ""                    # clarify/refuse/ask text
    answer: Optional[Answer] = None
    disclaimer: str = ""
    follow_ups: List[str] = field(default_factory=list)
    cross_hint: Optional[Dict[str, str]] = None


class Engine:
    def __init__(self):
        self.domains: Dict[str, DomainConfig] = load_domains()
        self.llm = LLMClient(llm_settings())
        self.store = KnowledgeStore()
        self.store.build(load_seed_corpus(), llm=self.llm)
        self.router = DomainRouter(self.domains, self.store)

    # --------------------------------------------------------- knowledge ---
    def add_document(self, data: bytes, filename: str, domain: str) -> int:
        chunks: List[Chunk] = ingest_upload(data, filename, domain)
        if chunks:
            self.store.add(chunks, llm=self.llm)
        return len(chunks)

    def stats(self) -> Dict[str, int]:
        return self.store.stats()

    # ---------------------------------------------------------- main loop ---
    def ask(self, query: str, pinned: Optional[str] = None,
            confirmed_domain: Optional[str] = None) -> Turn:
        # If the user confirmed a domain chip, treat it as a pin for this turn.
        effective_pin = confirmed_domain or pinned
        route = self.router.route(query, pinned=effective_pin)

        # 1) Too ambiguous -> ask the user to choose a domain.
        if route.mode == "ask" and not effective_pin:
            return Turn(query, route, status="ask_domain",
                        message="I'm not sure which area this is. Pick one:")

        domain = route.domain or (route.suggestions[0] if route.suggestions else None)
        if domain is None:
            return Turn(query, route, status="ask_domain",
                        message="I'm not sure which area this is. Pick one:")
        cfg = self.domains[domain]

        # 2) Suggest-mode (not pinned/confirmed) -> offer chips before answering.
        if route.mode == "suggest" and not effective_pin:
            return Turn(query, route, status="ask_domain", domain=domain,
                        message=f"Looks like {cfg.label}. Confirm the domain:")

        # 3) Guardrail refusal (out-of-scope ask).
        refusal = guardrails.refuse(cfg, query)
        if refusal:
            return Turn(query, route, status="refuse", domain=domain,
                        message=refusal, disclaimer=guardrails.disclaimer(cfg))

        # 4) Gap detection -> clarification loop.
        gap = guardrails.detect_gap(cfg, query)
        if gap:
            return Turn(query, route, status="clarify", domain=domain, message=gap)

        # 5) Retrieve (namespace-isolated) + compose grounded answer.
        retrieved = self.store.retrieve(query, domain)
        answer = compose(query, cfg, retrieved, self.llm)
        answer.text = guardrails.redact_pii(answer.text)

        # 6) Suggestions.
        fups = suggest.follow_ups(cfg, query, answer.text)
        hint = suggest.cross_domain_hint(cfg, query)

        return Turn(
            query, route, status="answer", domain=domain, answer=answer,
            disclaimer=guardrails.disclaimer(cfg), follow_ups=fups, cross_hint=hint,
        )

    # ----------------------------------------------------------- helpers ---
    def typeahead(self, prefix: str, domain: Optional[str]) -> List[str]:
        return suggest.typeahead(prefix, self.store, domain, domains=self.domains)
