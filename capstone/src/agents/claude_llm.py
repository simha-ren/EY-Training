"""Claude LLM integration for production use.

Resilient by design: if no API key is configured (or the Claude API errors),
the client transparently falls back to a deterministic, grounded extractive
mode so the chat *always* produces an answer instead of dying with
"Unable to generate answer". The ``online`` flag and ``last_error`` let the UI
show which mode produced a given answer.
"""
from __future__ import annotations

import os
import re
import json
from typing import Optional, List
from datetime import datetime

from anthropic import Anthropic

from src.common.metrics import extractive_answer, compute_groundedness


class ClaudeLLMClient:
    """Production-grade Claude LLM client with an offline fallback."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        # Accept either CLAUDE_API_KEY or the SDK-standard ANTHROPIC_API_KEY.
        self.api_key = (api_key or os.getenv("CLAUDE_API_KEY")
                        or os.getenv("ANTHROPIC_API_KEY") or "").strip()
        self.model = model
        self.last_error: Optional[str] = None
        self.online = bool(self.api_key)
        self.client = None
        if self.online:
            try:
                self.client = Anthropic(api_key=self.api_key)
            except Exception as exc:  # pragma: no cover - depends on env
                self.online = False
                self.last_error = str(exc)
        self.conversation_history: List[dict] = []

    # ------------------------------------------------------------------ raw
    def complete(self, system: str, user: str, temperature: float = 0.2,
                 max_tokens: int = 2048) -> Optional[str]:
        """Get a completion from Claude. Returns None (and sets last_error)
        when offline or on any API error, so callers can fall back."""
        if not self.online or self.client is None:
            self.last_error = self.last_error or "No Claude API key configured (offline mode)."
            return None
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            # Concatenate any text blocks in the response.
            parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
            self.last_error = None
            return "\n".join(parts).strip() if parts else None
        except Exception as e:
            self.last_error = str(e)
            print(f"Error calling Claude API: {e}")
            return None

    def chat(self, messages: List[dict], system: str = "", temperature: float = 0.7,
             max_tokens: int = 2048) -> Optional[str]:
        """Multi-turn conversation with Claude."""
        if not self.online or self.client is None:
            return None
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "You are a helpful AI assistant.",
                messages=messages,
            )
            parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
            return "\n".join(parts).strip() if parts else None
        except Exception as e:
            self.last_error = str(e)
            print(f"Error in chat: {e}")
            return None

    # -------------------------------------------------------------- analyze
    def analyze_document(self, document_content: str, analysis_type: str = "full") -> dict:
        """Analyze a document for objectives, challenges, solutions, insights."""
        prompt = f"""Analyze the following document and respond with ONLY a JSON object
(no prose, no markdown fences) using exactly these keys:
"objective" (string), "challenges" (array of strings),
"proposed_solutions" (array of strings), "insights" (array of strings),
"confidence" (number between 0 and 1).

Document Content:
{document_content}
"""
        response = self.complete(
            system="You are an expert analyst. Return strictly valid JSON.",
            user=prompt,
            temperature=0.3,
        )

        if response:
            parsed = self._extract_json(response)
            if isinstance(parsed, dict):
                parsed.setdefault("objective", "")
                parsed.setdefault("challenges", [])
                parsed.setdefault("proposed_solutions", [])
                parsed.setdefault("insights", [])
                parsed["confidence"] = self._normalize_confidence(parsed.get("confidence"))
                parsed["mode"] = "claude"
                return parsed
            # Got text but not JSON - keep it as raw analysis.
            return {
                "objective": "", "challenges": [], "proposed_solutions": [],
                "insights": [], "confidence": 0.5, "raw_analysis": response,
                "mode": "claude",
            }

        # ---- Offline extractive analysis -------------------------------
        return self._offline_analysis(document_content)

    def _offline_analysis(self, content: str) -> dict:
        from src.common.metrics import _split_sentences
        sentences = _split_sentences(content)
        objective = " ".join(sentences[:2]) if sentences else content[:300]

        def _pick(keywords: List[str], limit: int = 3) -> List[str]:
            hits = [s for s in sentences
                    if any(k in s.lower() for k in keywords)]
            return hits[:limit]

        challenges = _pick(["challenge", "problem", "risk", "gap", "issue",
                             "barrier", "constraint", "lack"], 3)
        solutions = _pick(["propose", "solution", "recommend", "should",
                            "improve", "implement", "plan", "strategy"], 3)
        insights = _pick(["increase", "decrease", "result", "impact",
                          "benefit", "growth", "%", "key"], 3)

        return {
            "objective": objective,
            "challenges": challenges or ["Not explicitly stated in the document."],
            "proposed_solutions": solutions or ["Not explicitly stated in the document."],
            "insights": insights or sentences[2:5] or ["No further insights extracted."],
            "confidence": 0.55,
            "mode": "offline",
        }

    # --------------------------------------------------------------- answer
    def answer_question(self, context: str, question: str,
                        confidence_threshold: float = 0.7,
                        allow_general_knowledge: bool = True) -> dict:
        """Answer a question, preferring the document but never dead-ending.

        - If the document contains the answer, answer from it (grounded).
        - If not, and allow_general_knowledge is True, answer from general
          knowledge, clearly labelled.
        - If the question is too vague/empty to answer, ask the user a
          clarifying question instead of returning a non-answer.
        Online uses Claude; offline uses a grounded extractive fallback.
        """
        # Empty / trivial question -> ask for clarification immediately.
        if not question or len(question.strip()) < 3:
            return self._clarify("Could you tell me what you'd like to know about "
                                  "the document? For example, its objective, risks, "
                                  "costs, or a specific section.")

        gk_clause = (
            "If the context does NOT contain the answer, you MAY answer from your "
            "general knowledge, but begin that part with '(General knowledge, not "
            "from the document):'."
            if allow_general_knowledge else
            "If the context does not contain the answer, say so plainly."
        )
        prompt = f"""You are answering a user's question about a document.
Prefer the context below and quote concrete figures or terms from it when possible.
{gk_clause}
If the question is too vague or ambiguous to answer well, do NOT guess: reply with
a single line beginning 'CLARIFY:' followed by one specific question that would let
you answer.
At the very end (unless you used CLARIFY), add a line exactly like: Confidence: NN%

Context:
{context}

Question: {question}
"""
        response = self.complete(
            system="You are a helpful domain expert. Be accurate, cite the document "
                   "when you can, and ask for clarification rather than guessing.",
            user=prompt,
            temperature=0.2,
        )

        if response:
            clar = self._detect_clarify(response)
            if clar:
                return self._clarify(clar, mode="claude")
            answer_text, confidence = self._strip_confidence(response)
            grounded = compute_groundedness(answer_text, context)
            if confidence is None:
                confidence = max(0.5, grounded)
            source = "general" if "general knowledge" in answer_text.lower() else "document"
            return {
                "answer": answer_text,
                "confidence": round(float(confidence), 3),
                "mode": "claude",
                "source": source,
                "needs_clarification": False,
                "used_fallback": False,
                "timestamp": datetime.now().isoformat(),
                "model": self.model,
            }

        # ---- Offline grounded fallback ---------------------------------
        fb = extractive_answer(question, context)
        # If the document clearly doesn't cover it, ask the user to refine
        # rather than returning a weak non-answer.
        if fb["confidence"] <= 0.3:
            return self._clarify(
                "I couldn't find that in the uploaded document. Could you rephrase, "
                "point me to the relevant section, or confirm you'd like a general "
                "answer? (Tip: enable 'Answer beyond the document' in the sidebar.)",
                mode="offline")
        return {
            "answer": fb["answer"],
            "confidence": fb["confidence"],
            "mode": "offline",
            "source": "document",
            "needs_clarification": False,
            "used_fallback": True,
            "note": self.last_error or "Answered from the document (offline mode).",
            "timestamp": datetime.now().isoformat(),
            "model": "extractive-fallback",
        }

    @staticmethod
    def _detect_clarify(text: str):
        """Return the clarifying question if the model asked to clarify."""
        m = re.search(r"CLARIFY:\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _clarify(message: str, mode: str = "offline") -> dict:
        return {
            "answer": message,
            "confidence": 0.0,
            "mode": mode,
            "source": "clarify",
            "needs_clarification": True,
            "used_fallback": mode == "offline",
            "timestamp": datetime.now().isoformat(),
            "model": "clarify",
        }

    # ---------------------------------------------------------- suggestions
    def get_auto_suggestions(self, context: str, last_query: str = "") -> List[str]:
        """Suggest 3-5 relevant follow-up questions. Falls back to heuristics."""
        prompt = f"""Based on the document context and the last query, suggest 3-5
short, relevant follow-up questions a reader might ask next.
Return ONLY a JSON array of strings, nothing else.

Context Summary:
{context[:800]}

Last Query: {last_query}
"""
        response = self.complete(
            system="Generate concise, relevant follow-up questions as a JSON array.",
            user=prompt,
            temperature=0.7,
            max_tokens=400,
        )
        if response:
            parsed = self._extract_json(response, expect="array")
            if isinstance(parsed, list) and parsed:
                return [str(q).strip() for q in parsed if str(q).strip()][:5]

        return self._offline_suggestions(context)

    def _offline_suggestions(self, context: str) -> List[str]:
        """Heuristic follow-ups derived from the document's own content."""
        suggestions: List[str] = []
        # Pull candidate topic phrases from headings / capitalised noun groups.
        lines = [l.strip(" #*-\t") for l in (context or "").splitlines()]
        headings = [l for l in lines if 3 <= len(l.split()) <= 8 and l[:1].isupper()]
        for h in headings[:3]:
            suggestions.append(f"What does the document say about {h.rstrip(':.')}?")
        generic = [
            "What is the main objective of this document?",
            "What challenges or risks are identified?",
            "What solutions or recommendations are proposed?",
            "What are the key figures or metrics mentioned?",
        ]
        for g in generic:
            if len(suggestions) >= 5:
                break
            if g not in suggestions:
                suggestions.append(g)
        return suggestions[:5]

    def validate_completeness(self, document_content: str) -> dict:
        prompt = f"""Review this document and identify what information is missing
or incomplete. Document:
{document_content}
"""
        response = self.complete(
            system="You are a compliance and completeness reviewer.",
            user=prompt,
            temperature=0.2,
        )
        return {
            "assessment": response or "Offline mode: automated completeness review unavailable.",
            "timestamp": datetime.now().isoformat(),
        }

    # ----------------------------------------------------------- internals
    @staticmethod
    def _extract_json(text: str, expect: str = "object"):
        """Best-effort JSON extraction from a model response."""
        if not text:
            return None
        # Strip markdown code fences if present.
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        candidate = fenced.group(1) if fenced else text
        pattern = r"\[.*\]" if expect == "array" else r"\{.*\}"
        match = re.search(pattern, candidate, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except Exception:
            return None

    @staticmethod
    def _normalize_confidence(value) -> float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return 0.5
        if v > 1.0:  # percentage form
            v = v / 100.0
        return round(max(0.0, min(1.0, v)), 3)

    @staticmethod
    def _strip_confidence(text: str):
        """Pull a 'Confidence: NN%' marker out of the answer if present.

        Returns (clean_answer, confidence_or_None).
        """
        confidence = None
        m = re.search(r"confidence\s*[:\-]?\s*([0-9]{1,3}(?:\.[0-9]+)?)\s*%?",
                      text, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1))
                confidence = min(1.0, val / 100.0 if val > 1 else val)
            except ValueError:
                confidence = None
            # Remove the confidence line from the displayed answer.
            text = re.sub(r"\n?\s*confidence\s*[:\-]?\s*[0-9.]+\s*%?.*$", "",
                          text, flags=re.IGNORECASE).strip()
        return text.strip(), confidence
