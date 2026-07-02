"""Unit tests for core.guardrails — PII redaction and safety checks."""
from core.guardrails import Guardrails, redact_pii, GuardrailType


def test_run_all_checks_returns_results():
    g = Guardrails()
    results = g.run_all_checks("The answer is 42.", query="what is the answer",
                               confidence=0.9, domain="general")
    assert isinstance(results, list)
    assert len(results) >= 1
    for r in results:
        assert hasattr(r, "guardrail_type")
        assert hasattr(r, "triggered")
        assert isinstance(r.triggered, bool)


def test_low_confidence_triggers_guardrail():
    g = Guardrails()
    results = g.run_all_checks("Vague answer.", query="q",
                               confidence=0.01, domain="general")
    conf = [r for r in results if r.guardrail_type == GuardrailType.CONFIDENCE_THRESHOLD]
    assert conf, "confidence guardrail should be present"
    assert conf[0].triggered is True


def test_redact_pii_masks_email_and_phone():
    text = "Reach me at john.doe@example.com or 9876543210."
    out = redact_pii(text, True)
    assert "john.doe@example.com" not in out
    assert "9876543210" not in out
    assert "redacted" in out.lower()


def test_redact_pii_noop_when_disabled():
    text = "Email: a@b.com"
    assert redact_pii(text, False) == text
