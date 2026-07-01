"""Domain Router (doc Section 2.2 - the signature layer).

Combines two cheap, transparent signals into a domain + confidence score:
  1. Lexical keyword evidence per domain (from each domain's config).
  2. TF-IDF centroid similarity of the query to each domain's knowledge.

Above ROUTE_CONFIDENT -> route silently. Between AMBIGUOUS and CONFIDENT ->
return autosuggest chips so the user confirms in one tap. Below AMBIGUOUS ->
ask the user to choose. Mirrors router/{classifier,confidence,autosuggest}.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import ROUTE_AMBIGUOUS, ROUTE_CONFIDENT, DomainConfig


@dataclass
class RouteResult:
    domain: Optional[str]            # chosen domain, or None when too ambiguous
    confidence: float                # 0..1 score for the top domain
    scores: Dict[str, float]         # per-domain blended score
    mode: str                        # "confident" | "suggest" | "ask"
    suggestions: List[str]           # ordered candidate domains for chips


def _keyword_score(query: str, cfg: DomainConfig) -> float:
    low = query.lower()
    hits = 0
    for kw in cfg.routing_keywords:
        # word-ish boundary match so 'fd' doesn't fire inside 'feedback'
        if re.search(r"(?<!\w)" + re.escape(kw.lower()) + r"(?!\w)", low):
            hits += 1
    if not cfg.routing_keywords:
        return 0.0
    # saturating: 1 hit already strong, diminishing returns after
    return min(1.0, 0.55 * hits + (0.15 if hits else 0.0))


class DomainRouter:
    def __init__(self, domains: Dict[str, DomainConfig], store):
        self.domains = domains
        self.store = store

    def route(self, query: str, pinned: Optional[str] = None) -> RouteResult:
        # A pinned domain overrides routing entirely (left-rail pin).
        if pinned and pinned in self.domains:
            return RouteResult(pinned, 1.0, {pinned: 1.0}, "confident", [])

        kw = {k: _keyword_score(query, cfg) for k, cfg in self.domains.items()}
        cen = self.store.domain_centroid_scores(query)
        # normalize centroid scores to 0..1 across domains
        if cen:
            mx = max(cen.values()) or 1.0
            cen = {k: (v / mx if mx > 0 else 0.0) for k, v in cen.items()}

        blended: Dict[str, float] = {}
        for k in self.domains:
            blended[k] = round(0.6 * kw.get(k, 0.0) + 0.4 * cen.get(k, 0.0), 4)

        ordered = sorted(blended.items(), key=lambda kv: kv[1], reverse=True)
        top_domain, top_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0.0
        margin = top_score - second_score

        if top_score >= ROUTE_CONFIDENT and margin >= 0.08:
            mode = "confident"
            suggestions: List[str] = []
            domain = top_domain
        elif top_score >= ROUTE_AMBIGUOUS:
            mode = "suggest"
            suggestions = [d for d, s in ordered if s >= ROUTE_AMBIGUOUS][:3] or [top_domain]
            domain = top_domain  # provisional; UI lets the user confirm/switch
        else:
            mode = "ask"
            suggestions = [d for d, _ in ordered][:3]
            domain = None

        return RouteResult(domain, round(top_score, 3), blended, mode, suggestions)
