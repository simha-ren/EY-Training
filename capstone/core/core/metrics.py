"""Shared evaluation metrics and a grounded extractive fallback.

This module centralises the three component scores the app uses to judge an
answer, so both the Streamlit UI (app_prod.py) and the FastAPI server
(api_server.py) compute accuracy identically:

  * groundedness - how much of the answer is supported by the source context
  * usefulness   - whether the answer is substantive (not a punt / too short)
  * confidence   - the model's (or fallback's) own confidence in the answer

accuracy_score is the mean of those three. It is intentionally simple,
transparent and dependency-free so it can run with no API key.

It also exposes ``extractive_answer`` - a deterministic, citation-style answer
built from the most relevant sentences of the document. The chat uses this as a
fallback whenever the LLM is offline or errors, so the app *always* produces a
grounded answer instead of a dead "Unable to generate answer".
"""
from __future__ import annotations

import re
from typing import List, Tuple

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Short, generic words that should not count towards relevance overlap.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "is", "are", "was", "were", "be", "been", "being", "this", "that",
    "these", "those", "it", "its", "as", "at", "by", "with", "from", "what",
    "which", "who", "whom", "how", "why", "when", "where", "do", "does", "did",
    "can", "could", "should", "would", "will", "shall", "may", "might", "i",
    "you", "we", "they", "he", "she", "about", "into", "than", "then",
}

_LOW_QUALITY_MARKERS = (
    "unable to", "i cannot", "i can't", "i do not know", "i don't know",
    "unknown", "no answer", "cannot answer", "not enough information",
)


def _tokens(text: str) -> List[str]:
    return [w for w in _WORD_RE.findall((text or "").lower())]


def _content_tokens(text: str) -> List[str]:
    return [w for w in _tokens(text) if w not in _STOPWORDS and len(w) > 1]


def compute_groundedness(answer: str, context: str) -> float:
    """Fraction of the answer's content words that also appear in the context.

    1.0 means every meaningful word is traceable to the source; near 0 means the
    answer is largely unsupported by the document.
    """
    answer_words = _tokens(answer)
    if not answer_words:
        return 0.0
    context_vocab = set(_tokens(context))
    overlap = sum(1 for w in answer_words if w in context_vocab)
    return round(min(1.0, overlap / len(answer_words)), 3)


# Backwards-compatible alias (older code used the "groundness" spelling).
compute_groundness = compute_groundedness


def compute_usefulness(answer: str) -> float:
    """Heuristic: substantive, on-topic answers score high; punts score low."""
    if not answer or not answer.strip():
        return 0.0
    low = answer.lower()
    if any(marker in low for marker in _LOW_QUALITY_MARKERS):
        return 0.1
    words = len(_tokens(answer))
    if words < 10:
        return 0.4
    if words < 25:
        return 0.7
    return 0.95


def compute_accuracy(confidence: float, groundedness: float, usefulness: float) -> float:
    """Composite accuracy = mean of confidence, groundedness, usefulness."""
    confidence = max(0.0, min(1.0, float(confidence or 0.0)))
    groundedness = max(0.0, min(1.0, float(groundedness or 0.0)))
    usefulness = max(0.0, min(1.0, float(usefulness or 0.0)))
    return round((confidence + groundedness + usefulness) / 3, 3)


def evaluate_answer(answer: str, context: str, confidence: float) -> dict:
    """Return all four scores in one call (used by the UI and the API)."""
    groundedness = compute_groundedness(answer, context)
    usefulness = compute_usefulness(answer)
    accuracy = compute_accuracy(confidence, groundedness, usefulness)
    return {
        "confidence": round(float(confidence or 0.0), 3),
        "groundedness": groundedness,
        "groundness": groundedness,  # alias kept for existing log readers
        "usefulness": usefulness,
        "accuracy_score": accuracy,
    }


def _split_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    return [s.strip() for s in _SENT_SPLIT_RE.split(cleaned) if len(s.strip()) > 20]


def rank_sentences(question: str, context: str, top_k: int = 4) -> List[Tuple[str, float]]:
    """Rank document sentences by overlap with the question's content words."""
    q_terms = set(_content_tokens(question))
    sentences = _split_sentences(context)
    if not sentences:
        return []
    scored: List[Tuple[str, float]] = []
    for sent in sentences:
        s_terms = _content_tokens(sent)
        if not s_terms:
            continue
        if q_terms:
            hits = sum(1 for w in s_terms if w in q_terms)
            score = hits / (len(q_terms) ** 0.5)
        else:
            # No usable question terms -> fall back to leading sentences.
            score = 0.0
        scored.append((sent, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    if q_terms and scored and scored[0][1] == 0.0:
        # Nothing matched the question; surface the opening of the document.
        return [(s, 0.0) for s in sentences[:top_k]]
    return scored[:top_k]


def extractive_answer(question: str, context: str, top_k: int = 4) -> dict:
    """Build a grounded answer from the most relevant sentences of the document.

    Used when no LLM is available. Returns an answer string plus a confidence
    derived from how strongly the document matched the question.
    """
    ranked = rank_sentences(question, context, top_k=top_k)
    if not ranked:
        return {
            "answer": "The document does not appear to contain information to answer "
                      "that question. Try rephrasing or uploading a more relevant file.",
            "confidence": 0.2,
            "used_fallback": True,
        }

    matched = [s for s, score in ranked if score > 0]
    if matched:
        body = " ".join(matched[:top_k])
        lead = "Based on the document:"
        # Confidence scales with how many question terms were matched.
        top_score = ranked[0][1]
        confidence = round(min(0.85, 0.45 + 0.1 * top_score), 3)
    else:
        body = " ".join(s for s, _ in ranked[:2])
        lead = "I couldn't find a direct match, but here is the most relevant context:"
        confidence = 0.3

    answer = f"{lead} {body}"
    return {"answer": answer, "confidence": confidence, "used_fallback": True}
