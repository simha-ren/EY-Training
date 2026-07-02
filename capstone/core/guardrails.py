"""Production-grade guardrails with PII detection, confidence checks, and safety measures."""
from __future__ import annotations

import re
from typing import Optional, Dict, List, Tuple
from enum import Enum


class GuardrailType(Enum):
    """Types of guardrails."""
    PII_DETECTION = "pii_detection"
    CONFIDENCE_THRESHOLD = "confidence_threshold"
    DOMAIN_MISMATCH = "domain_mismatch"
    IRRELEVANT_QUERY = "irrelevant_query"
    POLICY_VIOLATION = "policy_violation"


class GuardrailResult:
    """Result of guardrail check."""
    
    def __init__(self, triggered: bool, guardrail_type: GuardrailType, 
                 message: str = "", severity: str = "info", details: Dict = None):
        self.triggered = triggered
        self.guardrail_type = guardrail_type
        self.message = message
        self.severity = severity  # info, warning, error
        self.details = details or {}


class Guardrails:
    """Production guardrails for safety and compliance."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.min_confidence = self.config.get('min_confidence', 0.6)
        self.max_pii_tolerance = self.config.get('max_pii_tolerance', 0)

    def check_pii(self, text: str) -> GuardrailResult:
        """Check for personally identifiable information."""
        pii_found = []
        if re.findall(_PII_PATTERNS[0][0], text):
            pii_found.append('id')
        if re.findall(_PII_PATTERNS[1][0], text):
            pii_found.append('email')
        if re.findall(_PII_PATTERNS[2][0], text):
            pii_found.append('phone')
        if re.findall(_PII_PATTERNS[3][0], text):
            pii_found.append('ssn')
        if re.findall(_PII_PATTERNS[4][0], text):
            pii_found.append('credit_card')
        if re.findall(_PII_PATTERNS[5][0], text):
            pii_found.append('ip_address')
        triggered = len(pii_found) > self.max_pii_tolerance
        return GuardrailResult(
            triggered=triggered,
            guardrail_type=GuardrailType.PII_DETECTION,
            message=f"PII detected: {', '.join(pii_found)}" if pii_found else "",
            severity="error" if triggered else "warning",
            details={"pii_types": pii_found, "count": len(pii_found)}
        )

    def check_confidence(self, confidence_score: float) -> GuardrailResult:
        """Check if confidence meets threshold."""
        triggered = confidence_score < self.min_confidence
        return GuardrailResult(
            triggered=triggered,
            guardrail_type=GuardrailType.CONFIDENCE_THRESHOLD,
            message=f"Low confidence score: {confidence_score:.2%}" if triggered else "",
            severity="warning",
            details={"confidence_score": confidence_score, "threshold": self.min_confidence}
        )

    def check_domain_mismatch(self, detected_domain: str, pinned_domain: Optional[str], confidence: float) -> GuardrailResult:
        """Check for domain mismatches."""
        triggered = False
        message = ""
        severity = "info"
        if pinned_domain and detected_domain != pinned_domain and confidence < 0.5:
            triggered = True
            severity = "warning"
            message = f"Low confidence domain match: {detected_domain} != {pinned_domain}"
        return GuardrailResult(
            triggered=triggered,
            guardrail_type=GuardrailType.DOMAIN_MISMATCH,
            message=message,
            severity=severity,
            details={"detected_domain": detected_domain, "pinned_domain": pinned_domain, "confidence": confidence}
        )

    def check_policy_violation(self, content: str, domain: str) -> GuardrailResult:
        """Check domain-specific policy violations."""
        violations = []
        if domain == "finance" and re.search(r"\b(buy|sell|invest|portfolio)\b", content, re.IGNORECASE):
            if "disclaimer" not in content.lower() and "not financial advice" not in content.lower():
                violations.append("Missing investment disclaimer")
        if domain == "healthcare" and re.search(r"\b(diagnosed|treatment|medication|cure)\b", content, re.IGNORECASE):
            if "consult" not in content.lower() and "doctor" not in content.lower():
                violations.append("Missing medical consultation disclaimer")
        triggered = len(violations) > 0
        return GuardrailResult(
            triggered=triggered,
            guardrail_type=GuardrailType.POLICY_VIOLATION,
            message="; ".join(violations) if violations else "",
            severity="error" if triggered else "info",
            details={"violations": violations, "domain": domain}
        )

    def check_query_relevance(self, query: str, document_context: str, threshold: float = 0.3) -> GuardrailResult:
        """Check if query is relevant to document."""
        query_words = set(query.lower().split())
        context_words = set(document_context.lower().split()[:500])
        overlap = len(query_words & context_words) / len(query_words) if query_words else 0
        triggered = overlap < threshold
        return GuardrailResult(
            triggered=triggered,
            guardrail_type=GuardrailType.IRRELEVANT_QUERY,
            message=f"Low query relevance: {overlap:.1%}" if triggered else "",
            severity="warning",
            details={"relevance_score": overlap, "threshold": threshold}
        )

    def run_all_checks(self, text: str, query: str = "", confidence: float = 1.0, domain: str = "", detected_domain: str = "") -> List[GuardrailResult]:
        """Run all applicable guardrails."""
        results = [self.check_pii(text)]
        if confidence < 1.0:
            results.append(self.check_confidence(confidence))
        if domain:
            results.append(self.check_domain_mismatch(detected_domain, domain, confidence))
            results.append(self.check_policy_violation(text, domain))
        if query and text:
            results.append(self.check_query_relevance(query, text))
        return results

    def get_triggered_guardrails(self, results: List[GuardrailResult]) -> List[GuardrailResult]:
        """Get only triggered guardrails."""
        return [r for r in results if r.triggered]


# PII patterns
_PII_PATTERNS = [
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[redacted-id]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[redacted-email]"),
    (re.compile(r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"), "[redacted-phone]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[redacted-ssn]"),
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[redacted-cc]"),
    (re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"), "[redacted-ip]"),
]


# --- Sensitive PII / PHI request detection (input-side guardrail) -----------
_SENSITIVE_PII = {
    "a Social Security Number (SSN)": ["ssn", "social security number", "social security no"],
    "an Aadhaar number": ["aadhaar", "aadhar"],
    "a credit/debit card number": ["credit card number", "debit card number",
                                    "card number", "cvv", "card details"],
    "a bank account number": ["bank account number", "account number", "ifsc"],
    "a passport number": ["passport number", "passport no"],
    "a phone/mobile number": ["phone number", "mobile number", "contact number"],
    "an email address": ["email address", "email id", "e-mail address"],
    "a home address": ["home address", "residential address"],
    "a date of birth": ["date of birth", "dob"],
    "a password or credentials": ["password", "pin number", "one time password", "otp"],
    "a driver's license number": ["driver's license", "driving licence", "license number"],
}
_SENSITIVE_PHI = {
    "a medical/health record": ["medical record", "health record", "patient record"],
    "a diagnosis": ["diagnosis", "diagnosed with"],
    "prescription / medication details": ["prescription", "medication list", "medicines prescribed"],
    "lab / test results": ["lab results", "test results", "blood report"],
    "mental-health information": ["mental health history", "psychiatric record"],
    "treatment / medical history": ["treatment history", "medical history"],
}
# Terms sensitive enough to refuse on mere mention (no verb required).
_STRONG_TERMS = {"ssn", "social security number", "aadhaar", "aadhar", "cvv",
                 "credit card number", "debit card number", "passport number",
                 "password", "otp", "medical record", "health record",
                 "patient record", "diagnosis"}
_EXTRACT_VERBS = ["what is", "what's", "give me", "list", "show", "reveal",
                  "extract", "tell me", "provide", "find the", "share the",
                  "display", "fetch", "who is", "whose"]


def check_sensitive_request(query: str) -> Optional[GuardrailResult]:
    """Detect when the *user's question* asks to reveal/extract PII or PHI.

    Returns a triggered GuardrailResult naming the field/category, or None.
    """
    low = (query or "").lower()
    if not low.strip():
        return None
    has_verb = any(v in low for v in _EXTRACT_VERBS)
    # 1) Explicit, correctly-categorized PII/PHI terms first.
    for category, mapping in (("PII", _SENSITIVE_PII), ("PHI", _SENSITIVE_PHI)):
        for field, terms in mapping.items():
            for term in terms:
                if term in low and (has_verb or term in _STRONG_TERMS):
                    return GuardrailResult(
                        triggered=True,
                        guardrail_type=GuardrailType.PII_DETECTION,
                        message=(f"This request asks for {field}, which is sensitive "
                                 f"{category} (personal/health) information. I can't "
                                 f"reveal or extract that."),
                        severity="high",
                        details={"category": category, "field": field, "term": term},
                    )

    # 2) Soft phrasings that imply extracting identifiers without a hard keyword,
    # e.g. "what contact details are listed", "show the account information".
    _SOFT_SUBJECTS = ["personal", "contact", "account", "card", "bank", "kyc",
                      "identity", "identification", "customer", "applicant",
                      "patient", "insurance", "policy"]
    _HEALTH_SUBJECTS = {"patient", "clinical", "medical", "health", "diagnosis"}
    _SOFT_NOUNS = ["detail", "details", "information", "info", "data", "record", "records"]
    if any(s in low for s in _SOFT_SUBJECTS) and any(n in low for n in _SOFT_NOUNS):
        cat = "PHI" if any(h in low for h in _HEALTH_SUBJECTS) else "PII"
        return GuardrailResult(
            triggered=True, guardrail_type=GuardrailType.PII_DETECTION,
            message=(f"This request asks for personal/identifying details, which are "
                     f"sensitive {cat}. I can't reveal or extract that."),
            severity="high",
            details={"category": cat, "field": "personal/identifying details",
                     "term": "soft-phrasing"},
        )
    return None


def refuse(cfg: Optional[Dict] = None, query: str = "") -> Optional[str]:
    """Check if query violates domain policies."""
    if not cfg:
        return None
    patterns = cfg.get("refuse_patterns", []) or []
    low = query.lower()
    for p in patterns:
        if p.lower() in low:
            return cfg.get("refusal_message", "I can't help with that request.")
    return None


def redact_pii(text: str, enable_redaction: bool = True) -> str:
    """Mask PII in text."""
    if not enable_redaction:
        return text
    out = text
    for pat, repl in _PII_PATTERNS:
        out = pat.sub(repl, out)
    return out


def disclaimer(cfg: Optional[Dict] = None) -> str:
    """Get domain disclaimer."""
    if not cfg:
        return ""
    return cfg.get("disclaimer", "")


def detect_gap(cfg: Optional[Dict] = None, query: str = "") -> Optional[str]:
    """Return a clarifying question if a mandatory detail is missing."""
    if not cfg or not query:
        return None
    low = query.lower()
    clarify_config = cfg.get("clarify", {}) or {}
    for trig in clarify_config.get("triggers", []) or []:
        phrase = trig.get("phrase", "").lower()
        if phrase and phrase in low:
            return trig.get("ask")
    return None
