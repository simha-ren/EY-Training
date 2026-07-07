"""Autosuggest service (doc Section 2.2, the three layers).

Layer 1 (domain autosuggest) lives in router.py. This module covers:
  Layer 2 - query type-ahead drawn from indexed section headings/questions.
  Layer 3 - follow-up suggestions after an answer, plus cross-domain hops.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from src.common.config import DomainConfig


def typeahead(prefix: str, store, domain: Optional[str], limit: int = 5,
              domains: Optional[Dict[str, DomainConfig]] = None) -> List[str]:
    """Suggest questions the KB can actually answer.

    Pool = question-style follow-ups from the domain config (best) + indexed
    section headings (fallback), so prefixes like 'how' surface real questions.
    """
    prefix = (prefix or "").strip().lower()
    pool: List[str] = []
    seen = set()

    # 1) question-style suggestions from config (preferred)
    if domains:
        for k, cfg in domains.items():
            if domain and k != domain:
                continue
            for q in cfg.follow_ups:
                if q.lower() not in seen:
                    seen.add(q.lower())
                    pool.append(q)

    # 2) indexed section headings (fallback / discovery)
    for c in store.chunks:
        if domain and c.domain != domain:
            continue
        cand = c.section.strip()
        if not cand or cand.lower() in seen or cand.endswith(".md"):
            continue
        seen.add(cand.lower())
        pool.append(cand)

    if not prefix:
        return pool[:limit]
    starts = [p for p in pool if p.lower().startswith(prefix)]
    contains = [p for p in pool if prefix in p.lower() and p not in starts]
    return (starts + contains)[:limit]


def follow_ups(cfg: DomainConfig, query: str, answer_text: str, limit: int = 3) -> List[str]:
    """Return 2-3 domain-tuned follow-up questions, lightly filtered."""
    base = list(cfg.follow_ups)
    low_q = (query or "").lower()
    # de-prioritise a follow-up that the user effectively just asked
    base.sort(key=lambda f: 1 if any(w in low_q for w in f.lower().split()[:3]) else 0)
    return base[:limit]


def followups_from_last(llm, cfg: DomainConfig, query: str, answer_text: str,
                        limit: int = 3) -> List[str]:
    """Follow-up questions grounded in the LAST question and its answer.

    Uses the online LLM to propose natural next questions; falls back to the
    domain's curated follow-ups when the LLM is offline or returns nothing.
    """
    online = bool(getattr(llm, "online", False))
    complete = getattr(llm, "complete", None)
    if online and callable(complete) and (query or answer_text):
        prompt = (
            "You are helping a user explore a document. Based ONLY on their last "
            "question and the answer given, suggest "
            f"{limit} short, natural follow-up questions they are likely to ask "
            "next. Each must be a standalone question under 12 words. "
            "Return one per line, no numbering, no preamble.\n\n"
            f"Last question: {query}\n"
            f"Answer given: {answer_text[:1200]}\n"
        )
        try:
            raw = complete(prompt)
            if raw:
                out = []
                for line in raw.splitlines():
                    s = line.strip().lstrip("-•*0123456789. ").strip()
                    if len(s) > 4 and s.endswith("?") and s.lower() != (query or "").lower():
                        out.append(s)
                if out:
                    return out[:limit]
        except Exception:
            pass
    # Offline / fallback: curated domain follow-ups.
    return follow_ups(cfg, query, answer_text, limit)


def cross_domain_hint(cfg: DomainConfig, query: str) -> Optional[Dict[str, str]]:
    """Detect when the query implies a hop to another domain."""
    low = (query or "").lower()
    for hint in cfg.cross_domain_hint:
        phrase = hint.get("phrase", "").lower()
        if phrase and re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", low):
            return {"domain": hint["domain"], "text": hint["text"]}
    return None
