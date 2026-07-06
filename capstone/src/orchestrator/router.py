"""Domain router (capstone doc, Section 2.2: the routing decision).

Given a user query, decide which knowledge domain it belongs to. The decision
blends two cheap signals:

  * semantic proximity of the query to each domain's centroid in the shared
    TF-IDF space (from KnowledgeStore.domain_centroid_scores), and
  * lexical hits against each domain's configured ``routing_keywords``.

The blended top score is compared against two thresholds from config:
  * >= ROUTE_CONFIDENT           -> mode "route"   (answer silently)
  * >= ROUTE_AMBIGUOUS           -> mode "suggest" (offer a domain chip)
  * <  ROUTE_AMBIGUOUS           -> mode "ask"     (ask the user to pick)

A pinned/confirmed domain short-circuits everything and routes directly.
The Engine (core/engine.py) consumes ``mode``, ``domain`` and ``suggestions``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.common.config import DomainConfig, ROUTE_CONFIDENT, ROUTE_AMBIGUOUS


@dataclass
class RouteResult:
    """Outcome of a routing decision."""
    mode: str                                   # route | suggest | ask
    domain: Optional[str] = None                # winning domain key (if any)
    suggestions: List[str] = field(default_factory=list)  # ranked domain keys
    confidence: float = 0.0                     # blended score of the winner
    scores: Dict[str, float] = field(default_factory=dict)


class DomainRouter:
    """Classifies a query into one of the configured domains."""

    # How much a single keyword hit contributes, and its cap.
    KEYWORD_WEIGHT = 0.18
    KEYWORD_CAP = 0.54
    # Minimum lead the top domain needs over the runner-up to route silently.
    MARGIN = 0.05

    def __init__(self, domains: Dict[str, DomainConfig], store):
        self.domains = domains
        self.store = store

    # ------------------------------------------------------------------ api
    def route(self, query: str, pinned: Optional[str] = None) -> RouteResult:
        # A pinned/confirmed domain wins outright.
        if pinned and pinned in self.domains:
            return RouteResult(mode="route", domain=pinned,
                               suggestions=[pinned], confidence=1.0)

        scores = self._score(query or "")
        if not scores:
            # No index yet / no signal -> let the user choose.
            return RouteResult(mode="ask", suggestions=list(self.domains.keys()))

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top_key, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        suggestions = [k for k, _ in ranked]

        # Confident: clear winner with enough of a lead -> answer directly.
        if top_score >= ROUTE_CONFIDENT and (top_score - second_score) >= self.MARGIN:
            return RouteResult(mode="route", domain=top_key,
                               suggestions=suggestions, confidence=top_score,
                               scores=scores)

        # Plausible but not certain -> offer a confirmation chip.
        if top_score >= ROUTE_AMBIGUOUS:
            return RouteResult(mode="suggest", domain=top_key,
                               suggestions=suggestions[:3], confidence=top_score,
                               scores=scores)

        # Too weak -> ask the user to pick a domain.
        return RouteResult(mode="ask", suggestions=suggestions,
                           confidence=top_score, scores=scores)

    # -------------------------------------------------------------- scoring
    def _score(self, query: str) -> Dict[str, float]:
        """Blend semantic centroid similarity with keyword hits, per domain."""
        semantic: Dict[str, float] = {}
        try:
            semantic = self.store.domain_centroid_scores(query) or {}
        except Exception:
            semantic = {}

        q = query.lower()
        blended: Dict[str, float] = {}
        for key, cfg in self.domains.items():
            sem = float(semantic.get(key, 0.0))
            hits = sum(1 for kw in getattr(cfg, "routing_keywords", [])
                       if kw and kw.lower() in q)
            kw_bonus = min(self.KEYWORD_CAP, self.KEYWORD_WEIGHT * hits)
            blended[key] = round(min(1.0, sem + kw_bonus), 4)
        return blended
