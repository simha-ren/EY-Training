"""Tests for guardrails + PII redaction."""
from core.core.guardrails import Guardrails, redact_pii


def test_run_all_checks_returns_results():
    results = Guardrails().run_all_checks("A grounded answer about the document.",
                                          query="what is it?", confidence=0.8,
                                          domain="general")
    assert isinstance(results, list) and len(results) >= 1
    assert all(hasattr(r, "triggered") for r in results)


def test_low_confidence_triggers_a_guardrail():
    results = Guardrails().run_all_checks("Maybe.", query="q", confidence=0.05,
                                          domain="general")
    assert any(r.triggered for r in results)


def test_redact_pii_masks_email():
    out = redact_pii("Contact me at john.doe@example.com please.")
    assert "john.doe@example.com" not in out


def test_sensitive_request_blocks_pii():
    from core.core.guardrails import check_sensitive_request
    r = check_sensitive_request("What is the SSN of the applicant?")
    assert r is not None and r.triggered and r.details["category"] == "PII"


def test_sensitive_request_blocks_phi():
    from core.core.guardrails import check_sensitive_request
    r = check_sensitive_request("give me the patient's medical record")
    assert r is not None and r.details["category"] == "PHI"


def test_sensitive_request_allows_benign():
    from core.core.guardrails import check_sensitive_request
    assert check_sensitive_request("What is the objective of the scheme?") is None


def test_soft_phrasing_blocked():
    from core.core.guardrails import check_sensitive_request
    assert check_sensitive_request("what contact details are listed?") is not None
    assert check_sensitive_request("show the account information") is not None
    assert check_sensitive_request("what personal details are there?") is not None


def test_output_pii_detected():
    g = Guardrails()
    leak = "Email rohan@example.com and card 4111 1111 1111 1111."
    assert g.check_pii(leak).triggered is True
    assert g.check_pii("Loan objective is home renovation.").triggered is False
