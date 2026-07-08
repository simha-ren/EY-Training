"""Compliance / Requirements Traceability Matrix (Kiro SDD — .kiro/specs/compliance-matrix/).

Extract requirements from an RFP, trace each to the proposal response, and report
coverage (Covered / Partial / Missing) with evidence and an overall compliance %.
Pure-Python, deterministic, no API key required. An online LLM may summarise gaps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

COVERED_T = 0.5
PARTIAL_T = 0.2

_MODAL = re.compile(r"\b(shall|must|required to|is required|should)\b", re.I)
_LIST = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "that",
    "this", "these", "those", "be", "is", "are", "will", "shall", "must", "should",
    "system", "provide", "support", "able", "user", "users", "which", "their",
    "have", "has", "each", "any", "all", "from", "into", "such", "within", "via",
}


@dataclass
class Requirement:
    id: str
    text: str
    keywords: List[str]


@dataclass
class MatrixRow:
    id: str
    requirement: str
    status: str
    score: float
    evidence: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "requirement": self.requirement,
                "status": self.status, "score": self.score, "evidence": self.evidence}


@dataclass
class MatrixResult:
    rows: List[MatrixRow] = field(default_factory=list)
    summary: Dict[str, float] = field(default_factory=dict)
    gaps: List[MatrixRow] = field(default_factory=list)
    gap_summary: str = ""

    def to_dict(self) -> dict:
        return {"rows": [r.to_dict() for r in self.rows], "summary": self.summary,
                "gaps": [g.to_dict() for g in self.gaps], "gap_summary": self.gap_summary}


def _words(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", (text or "").lower())


def _keywords(text: str) -> List[str]:
    seen, out = set(), []
    for w in _words(text):
        if len(w) >= 4 and w not in _STOP and w not in seen:
            seen.add(w); out.append(w)
    return out


def _split_units(text: str):
    """Yield (unit, is_list_item) in document order: sentences + list items."""
    units = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _LIST.match(line)
        if m:
            units.append((m.group(1).strip(), True))
            continue
        for piece in re.split(r"(?<=[.!?])\s+", line):
            piece = piece.strip()
            if piece:
                units.append((piece, False))
    return units


def extract_requirements(rfp_text: str) -> List[Requirement]:
    reqs: List[Requirement] = []
    seen = set()
    n = 0
    for unit, is_list in _split_units(rfp_text):
        is_modal = bool(_MODAL.search(unit))
        # A plain sentence must be an obligation (modal). A list item counts if
        # it is substantive (>=4 words) even without a modal verb.
        if not (is_modal or (is_list and len(unit.split()) >= 4)):
            continue
        norm = re.sub(r"\s+", " ", unit).strip().rstrip(".")
        key = norm.lower()
        if not norm or key in seen:
            continue
        kws = _keywords(norm)
        if not kws:
            continue
        seen.add(key)
        n += 1
        reqs.append(Requirement(id=f"R{n}", text=norm, keywords=kws))
    return reqs


def _best_match(keywords: List[str], response: str):
    if not keywords:
        return 0.0, ""
    best_score, best_sent = 0.0, ""
    for sent in re.split(r"(?<=[.!?])\s+|\n+", response or ""):
        sw = set(_words(sent))
        if not sw:
            continue
        hits = sum(1 for k in keywords if k in sw)
        score = hits / len(keywords)
        if score > best_score:
            best_score, best_sent = score, sent.strip()
    return round(best_score, 3), (best_sent if best_score > 0 else "")


def build_matrix(rfp_text: str, response_text: str, llm=None) -> MatrixResult:
    """Assemble the traceability matrix. Never raises."""
    reqs = extract_requirements(rfp_text or "")
    rows: List[MatrixRow] = []
    for r in reqs:
        score, evidence = _best_match(r.keywords, response_text or "")
        status = ("Covered" if score >= COVERED_T
                  else "Partial" if score >= PARTIAL_T else "Missing")
        rows.append(MatrixRow(r.id, r.text, status, score,
                              evidence if status != "Missing" else ""))
    total = len(rows)
    covered = sum(1 for r in rows if r.status == "Covered")
    partial = sum(1 for r in rows if r.status == "Partial")
    missing = sum(1 for r in rows if r.status == "Missing")
    pct = round(100 * covered / total) if total else 0
    summary = {"total": total, "covered": covered, "partial": partial,
               "missing": missing, "compliance_pct": pct}
    gaps = sorted([r for r in rows if r.status != "Covered"], key=lambda x: x.score)
    gap_summary = (f"{len(gaps)} gap(s): {missing} missing, {partial} partial."
                   if gaps else "Full coverage — no gaps.")
    if gaps and llm is not None and getattr(llm, "online", False) and hasattr(llm, "complete"):
        try:
            top = "; ".join(g.requirement[:80] for g in gaps[:3])
            r = llm.complete("You are a proposal compliance reviewer. One sentence.",
                             f"Summarise the top compliance gaps to address: {top}")
            if r:
                gap_summary = r.strip()
        except Exception:
            pass
    return MatrixResult(rows=rows, summary=summary, gaps=gaps, gap_summary=gap_summary)
