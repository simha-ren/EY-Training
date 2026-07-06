"""Groq LLM client (OpenAI-compatible) with the same interface as
ClaudeLLMClient, so app_prod.py / api_server.py can use Groq as the backend.

Groq exposes an OpenAI-compatible endpoint, so we drive it through the ``openai``
SDK by pointing base_url at https://api.groq.com/openai/v1. If no GROQ_API_KEY
is set or the call errors, methods return None / fall back exactly like the
Claude client, so the app's grounded offline mode still kicks in.
"""
from __future__ import annotations

import os
import re
import json
from typing import Optional, List
from datetime import datetime

from .metrics import extractive_answer, compute_groundedness

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqLLMClient:
    """OpenAI-compatible Groq client mirroring ClaudeLLMClient's interface."""

    def __init__(self, api_key: Optional[str] = None,
                 model: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = (api_key or os.getenv("GROQ_API_KEY") or "").strip()
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.base_url = base_url or GROQ_BASE_URL
        self.last_error: Optional[str] = None
        self.last_usage: Optional[dict] = None
        self.online = bool(self.api_key)
        self.client = None
        if self.online:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception as exc:  # pragma: no cover - depends on env
                self.online = False
                self.last_error = str(exc)
        self.conversation_history: List[dict] = []

    # ------------------------------------------------------------------ raw
    def complete(self, system: str, user: str, temperature: float = 0.2,
                 max_tokens: int = 2048) -> Optional[str]:
        if not self.online or self.client is None:
            self.last_error = self.last_error or "No Groq API key configured (offline mode)."
            return None
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            self.last_error = None
            usage = getattr(resp, "usage", None)
            if usage is not None:
                self.last_usage = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(usage, "completion_tokens", 0),
                    "total_tokens": getattr(usage, "total_tokens", 0),
                }
            return (resp.choices[0].message.content or "").strip() or None
        except Exception as e:
            self.last_error = str(e)
            print(f"Error calling Groq API: {e}")
            return None

    def chat(self, messages: List[dict], system: str = "", temperature: float = 0.7,
             max_tokens: int = 2048) -> Optional[str]:
        if not self.online or self.client is None:
            return None
        try:
            full = [{"role": "system", "content": system or "You are a helpful AI assistant."}]
            full.extend(messages)
            resp = self.client.chat.completions.create(
                model=self.model, temperature=temperature,
                max_tokens=max_tokens, messages=full,
            )
            return (resp.choices[0].message.content or "").strip() or None
        except Exception as e:
            self.last_error = str(e)
            print(f"Error in chat: {e}")
            return None

    # -------------------------------------------------------------- analyze
    def analyze_document(self, document_content: str, analysis_type: str = "full") -> dict:
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
            user=prompt, temperature=0.3,
        )
        if response:
            parsed = self._extract_json(response)
            if isinstance(parsed, dict):
                parsed.setdefault("objective", "")
                parsed.setdefault("challenges", [])
                parsed.setdefault("proposed_solutions", [])
                parsed.setdefault("insights", [])
                parsed["confidence"] = self._normalize_confidence(parsed.get("confidence"))
                parsed["mode"] = "groq"
                return parsed
            return {"objective": "", "challenges": [], "proposed_solutions": [],
                    "insights": [], "confidence": 0.5, "raw_analysis": response,
                    "mode": "groq"}
        return self._offline_analysis(document_content)

    def _offline_analysis(self, content: str) -> dict:
        from .metrics import _split_sentences
        sentences = _split_sentences(content)
        objective = " ".join(sentences[:2]) if sentences else content[:300]

        def _pick(keywords, limit=3):
            return [s for s in sentences if any(k in s.lower() for k in keywords)][:limit]

        return {
            "objective": objective,
            "challenges": _pick(["challenge", "problem", "risk", "gap", "issue",
                                 "barrier", "constraint", "lack"]) or ["Not explicitly stated."],
            "proposed_solutions": _pick(["propose", "solution", "recommend", "should",
                                         "improve", "implement", "plan", "strategy"]) or ["Not explicitly stated."],
            "insights": _pick(["increase", "decrease", "result", "impact", "benefit",
                               "growth", "%", "key"]) or sentences[2:5] or ["No further insights."],
            "confidence": 0.55, "mode": "offline",
        }

    # --------------------------------------------------------------- answer
    def answer_question(self, context: str, question: str,
                        confidence_threshold: float = 0.7,
                        allow_general_knowledge: bool = True) -> dict:
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
            user=prompt, temperature=0.2,
        )
        if response:
            clar = self._detect_clarify(response)
            if clar:
                return self._clarify(clar, mode="groq")
            answer_text, confidence = self._strip_confidence(response)
            if confidence is None:
                confidence = max(0.5, compute_groundedness(answer_text, context))
            source = "general" if "general knowledge" in answer_text.lower() else "document"
            return {"answer": answer_text, "confidence": round(float(confidence), 3),
                    "mode": "groq", "source": source, "needs_clarification": False,
                    "used_fallback": False,
                    "tokens": (self.last_usage or {}).get("total_tokens", 0),
                    "timestamp": datetime.now().isoformat(), "model": self.model}

        fb = extractive_answer(question, context)
        if fb["confidence"] <= 0.3:
            return self._clarify(
                "I couldn't find that in the uploaded document. Could you rephrase, "
                "point me to the relevant section, or confirm you'd like a general "
                "answer? (Tip: enable 'Answer beyond the document' in the sidebar.)",
                mode="offline")
        return {"answer": fb["answer"], "confidence": fb["confidence"],
                "mode": "offline", "source": "document", "needs_clarification": False,
                "used_fallback": True,
                "note": self.last_error or "Answered from the document (offline mode).",
                "timestamp": datetime.now().isoformat(), "model": "extractive-fallback"}

    @staticmethod
    def _detect_clarify(text: str):
        m = re.search(r"CLARIFY:\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _clarify(message: str, mode: str = "offline") -> dict:
        return {"answer": message, "confidence": 0.0, "mode": mode,
                "source": "clarify", "needs_clarification": True,
                "used_fallback": mode == "offline",
                "timestamp": datetime.now().isoformat(), "model": "clarify"}

    # ---------------------------------------------------------- suggestions
    def get_auto_suggestions(self, context: str, last_query: str = "") -> List[str]:
        prompt = f"""Based on the document context and the last query, suggest 3-5
short, relevant follow-up questions a reader might ask next.
Return ONLY a JSON array of strings, nothing else.

Context Summary:
{context[:800]}

Last Query: {last_query}
"""
        response = self.complete(
            system="Generate concise, relevant follow-up questions as a JSON array.",
            user=prompt, temperature=0.7, max_tokens=400,
        )
        if response:
            parsed = self._extract_json(response, expect="array")
            if isinstance(parsed, list) and parsed:
                return [str(q).strip() for q in parsed if str(q).strip()][:5]
        return self._offline_suggestions(context)

    def _offline_suggestions(self, context: str) -> List[str]:
        suggestions: List[str] = []
        lines = [l.strip(" #*-\t") for l in (context or "").splitlines()]
        headings = [l for l in lines if 3 <= len(l.split()) <= 8 and l[:1].isupper()]
        for h in headings[:3]:
            suggestions.append(f"What does the document say about {h.rstrip(':.')}?")
        for g in ["What is the main objective of this document?",
                  "What challenges or risks are identified?",
                  "What solutions or recommendations are proposed?",
                  "What are the key figures or metrics mentioned?"]:
            if len(suggestions) >= 5:
                break
            if g not in suggestions:
                suggestions.append(g)
        return suggestions[:5]

    def validate_completeness(self, document_content: str) -> dict:
        response = self.complete(
            system="You are a compliance and completeness reviewer.",
            user=f"Review this document and identify what is missing:\n{document_content}",
            temperature=0.2,
        )
        return {"assessment": response or "Offline mode: review unavailable.",
                "timestamp": datetime.now().isoformat()}

    # ----------------------------------------------------------- internals
    @staticmethod
    def _extract_json(text: str, expect: str = "object"):
        if not text:
            return None
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
        if v > 1.0:
            v = v / 100.0
        return round(max(0.0, min(1.0, v)), 3)

    @staticmethod
    def _strip_confidence(text: str):
        confidence = None
        m = re.search(r"confidence\s*[:\-]?\s*([0-9]{1,3}(?:\.[0-9]+)?)\s*%?",
                      text, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1))
                confidence = min(1.0, val / 100.0 if val > 1 else val)
            except ValueError:
                confidence = None
            text = re.sub(r"\n?\s*confidence\s*[:\-]?\s*[0-9.]+\s*%?.*$", "",
                          text, flags=re.IGNORECASE).strip()
        return text.strip(), confidence
