"""Grounded Composer (doc: Action/Generation Agent, Section 2.2).

Drafts an answer strictly from retrieved chunks and attaches inline citations
[1], [2]... mapped to source documents. Two paths:
  - LLM path: prompt a model with the numbered context and a strict
    'use only this context, cite with [n]' instruction.
  - Offline path: deterministic extractive composition from the top chunks,
    so the app is fully grounded and citation-backed with no API key.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

from .config import DomainConfig
from .ingestion import Chunk


@dataclass
class Citation:
    n: int
    source: str
    section: str
    chunk_id: str
    snippet: str


@dataclass
class Answer:
    text: str
    citations: List[Citation] = field(default_factory=list)
    grounded: bool = True
    used_llm: bool = False


def _build_context(chunks: List[Tuple[Chunk, float]]):
    cites, blocks = [], []
    for i, (chunk, _score) in enumerate(chunks, start=1):
        snippet = chunk.text.strip().replace("\n", " ")
        cites.append(
            Citation(
                n=i, source=chunk.source, section=chunk.section,
                chunk_id=chunk.id, snippet=snippet[:240],
            )
        )
        blocks.append(f"[{i}] (source: {chunk.source} - {chunk.section})\n{chunk.text.strip()}")
    return cites, "\n\n".join(blocks)


def _first_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n]).strip()


def compose(
    query: str,
    cfg: DomainConfig,
    retrieved: List[Tuple[Chunk, float]],
    llm,
) -> Answer:
    if not retrieved:
        return Answer(
            text="I don't have grounded knowledge for that in this domain yet. "
                 "Try rephrasing, or add a relevant document via the knowledge panel.",
            citations=[], grounded=False, used_llm=False,
        )

    citations, context = _build_context(retrieved)

    # ---- LLM path -------------------------------------------------------
    if getattr(llm, "online", False):
        system = (
            f"{cfg.persona}\n"
            "Answer ONLY using the numbered context. Cite each factual sentence "
            "with the matching [n]. If the context does not cover the question, "
            "say so plainly. Do not invent facts, numbers, or sources."
        )
        user = f"Question: {query}\n\nContext:\n{context}\n\nGrounded answer with [n] citations:"
        out = llm.complete(system, user)
        if out:
            return Answer(text=out.strip(), citations=citations, grounded=True, used_llm=True)

    # ---- Offline extractive path ---------------------------------------
    lines = [f"Here's what the {cfg.label} knowledge base says:\n"]
    for c in citations:
        lines.append(f"- {_first_sentences(c.snippet, 2)} [{c.n}]")
    text = "\n".join(lines)
    return Answer(text=text, citations=citations, grounded=True, used_llm=False)
