# Task List: Compliance / Requirements Traceability Matrix

> SDD — Phase 3 of 3: **Task Breakdown & Execution**
> Derived from `design.md`. States flip `[ ]` → `[x]` as each DoD clears.

## Wave 1 — Extraction (no dependencies)
- [x] **Task 1: `extract_requirements(rfp_text)`**
  - Sentence + list-item splitting; modal regex; ≥4-word list items; de-dup;
    sequential IDs; keyword derivation (stopword-filtered).
  - *DoD:* unit tests — modal sentences and list items captured; duplicate lines
    collapsed; IDs are `R1..Rn` in order.

## Wave 2 — Matching & scoring (depends on Wave 1)
- [x] **Task 2: coverage classifier**
  - Per-requirement max sentence overlap → score + evidence; thresholds →
    Covered / Partial / Missing.
  - *DoD:* exact-term response → Covered; partial → Partial; unrelated → Missing;
    empty response → all Missing.

## Wave 3 — Assemble matrix (depends on Wave 2)
- [x] **Task 3: `build_matrix(rfp_text, response_text, llm=None)`**
  - Rows + summary (totals, compliance_pct) + gaps (worst-first) + gap_summary;
    optional LLM one-liner (never required).
  - *DoD:* compliance_pct arithmetic correct; gaps sorted ascending by score;
    deterministic for identical inputs.

## Wave 4 — Exposure (depends on Wave 3)
- [x] **Task 4: API endpoint**
  - `POST /api/v1/compliance/matrix` in `api_server.py`.
  - *DoD:* returns rows, summary, gaps for `{rfp_text, response_text}`.
- [x] **Task 5: UI tab + audit**
  - "📋 Compliance" tab in `app_prod.py`: RFP + response inputs, matrix table with
    status badges, compliance-% metric, gap list; `COMPLIANCE_MATRIX` audit entry.
  - *DoD:* app runs end-to-end (Streamlit AppTest) with no exception.

## Wave 5 — Verify (depends on Wave 4)
- [x] **Task 6: Tests**
  - `tests/test_compliance_matrix.py` covering Waves 1–3.
  - *DoD:* full suite green.

## Execution log
```
[x] Task 1  extract_requirements ..... unit tests pass
[x] Task 2  coverage classifier ...... Covered/Partial/Missing verified
[x] Task 3  build_matrix ............. compliance_pct + gaps verified
[x] Task 4  API endpoint ............. returns full matrix
[x] Task 5  UI tab + audit ........... AppTest: no exception
[x] Task 6  tests .................... suite green
All tasks checked off ✅
```
