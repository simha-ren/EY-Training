# Requirements: Compliance / Requirements Traceability Matrix

> Spec-Driven Development (SDD) — Phase 1 of 3: **Requirements Gathering**
> Feature: extract requirements from an RFP and trace each to the proposal
> response with a coverage status, producing an auditable compliance matrix.
> Status: ✅ Approved — proceed to `design.md`.

## Context & Intent
Evaluators score proposals on whether every RFP requirement is addressed. Teams
currently track this by hand, which is slow and error-prone. This feature builds
the traceability matrix automatically: requirement → response → status → evidence.

## Requirements & Behavioral Logic

### Requirement 1: Requirement extraction
**User Story:** As a proposal manager, I want each discrete RFP requirement pulled
out and given a stable ID, so nothing is missed.

#### Acceptance Criteria (EARS)
- WHEN the RFP text contains a sentence with a modal obligation
  (`shall`, `must`, `required to`, `should`), THEN the system SHALL extract it as
  a requirement.
- WHEN the RFP contains numbered or bulleted list items, THEN the system SHALL
  extract each item as a requirement.
- WHEN requirements are extracted, THEN the system SHALL assign sequential stable
  IDs (`R1`, `R2`, …) in document order and de-duplicate identical statements.

### Requirement 2: Coverage classification with evidence
**User Story:** As a manager, I want to know if each requirement is Covered,
Partially covered, or Missing in our response, with the matching text as proof.

#### Acceptance Criteria (EARS)
- WHEN a requirement's key terms are strongly present in the response, THEN the
  system SHALL mark it **Covered** and attach the matching response snippet.
- IF only some key terms are present, THEN the system SHALL mark it **Partial**.
- WHEN no meaningful match is found, THEN the system SHALL mark it **Missing**
  with empty evidence.

### Requirement 3: Compliance summary
**User Story:** As a manager, I want a single compliance percentage and the list
of gaps to fix.

#### Acceptance Criteria (EARS)
- WHEN the matrix is built, THEN the system SHALL report totals (covered / partial
  / missing) and a **compliance percentage** = covered ÷ total.
- WHEN there are Missing or Partial items, THEN the system SHALL return them as a
  prioritised gap list.

### Requirement 4: Deterministic, key-free core
#### Acceptance Criteria (EARS)
- The extraction and matching SHALL be deterministic (same inputs → same matrix)
  and SHALL NOT require any API key. An online LLM MAY summarise gaps but SHALL
  never be required.

### Requirement 5: Never crash
#### Acceptance Criteria (EARS)
- WHEN the RFP or response text is empty or malformed, THEN the system SHALL
  return a valid (possibly empty) matrix without raising.

## Kiro Quality Gate 1
> Code generation paused. Operator verified edge cases: empty RFP → empty matrix;
> duplicate requirement lines collapsed; a requirement with partial term overlap →
> Partial (not Covered); list items without modals still captured.
> **Approved → generate technical design.**
