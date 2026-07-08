"""Tests for the Compliance Traceability Matrix (.kiro/specs/compliance-matrix/)."""
from src.agents.compliance_matrix import (
    extract_requirements, build_matrix, COVERED_T, PARTIAL_T)


RFP = """The system shall encrypt all data at rest.
The vendor must provide 24/7 support.
Reporting requirements:
- Provide a monthly usage dashboard for administrators
- Export audit logs in CSV format
The weather is nice today.
"""


# ------------------------------- extraction -------------------------------- #
def test_extracts_modal_and_list_requirements():
    reqs = extract_requirements(RFP)
    texts = " ".join(r.text.lower() for r in reqs)
    assert "encrypt all data at rest" in texts       # modal 'shall'
    assert "24/7 support" in texts                    # modal 'must'
    assert "monthly usage dashboard" in texts         # list item
    assert "export audit logs" in texts               # list item


def test_non_requirement_sentence_excluded():
    reqs = extract_requirements(RFP)
    assert all("weather" not in r.text.lower() for r in reqs)


def test_ids_are_sequential():
    reqs = extract_requirements(RFP)
    assert [r.id for r in reqs] == [f"R{i+1}" for i in range(len(reqs))]


def test_duplicates_collapsed():
    reqs = extract_requirements("The system must log events.\nThe system must log events.")
    assert len(reqs) == 1


def test_empty_rfp_returns_no_requirements():
    assert extract_requirements("") == []


# --------------------------------- matrix ---------------------------------- #
def test_covered_partial_missing():
    response = (
        "Our platform encrypts all data at rest using AES-256. "
        "We provide a monthly usage dashboard for administrators."
    )
    m = build_matrix(RFP, response)
    by_kw = {r.requirement.lower(): r for r in m.rows}
    enc = next(r for k, r in by_kw.items() if "encrypt" in k)
    dash = next(r for k, r in by_kw.items() if "dashboard" in k)
    supp = next(r for k, r in by_kw.items() if "support" in k)
    assert enc.status == "Covered" and enc.evidence
    assert dash.status == "Covered"
    assert supp.status == "Missing"          # 24/7 support not addressed


def test_empty_response_all_missing():
    m = build_matrix(RFP, "")
    assert all(r.status == "Missing" for r in m.rows)
    assert m.summary["compliance_pct"] == 0


def test_summary_and_compliance_pct():
    response = "We encrypt all data at rest. We provide 24/7 support. Monthly usage dashboard included. Audit logs export to CSV."
    m = build_matrix(RFP, response)
    s = m.summary
    assert s["total"] == s["covered"] + s["partial"] + s["missing"]
    assert 0 <= s["compliance_pct"] <= 100


def test_gaps_sorted_worst_first():
    m = build_matrix(RFP, "We encrypt all data at rest.")
    scores = [g.score for g in m.gaps]
    assert scores == sorted(scores)          # ascending (worst first)


def test_deterministic():
    a = build_matrix(RFP, "We encrypt data and provide dashboards.").to_dict()
    b = build_matrix(RFP, "We encrypt data and provide dashboards.").to_dict()
    assert a == b
