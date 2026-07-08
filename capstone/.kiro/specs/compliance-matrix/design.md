# Technical Design: Compliance / Requirements Traceability Matrix

> SDD — Phase 2 of 3: **Technical Design**
> Derived from `requirements.md`. Status: ✅ Approved — proceed to `tasks.md`.

## Module
`src/agents/compliance_matrix.py` — pure-Python, dependency-free. No API key
required; an online LLM may enrich the gap summary only.

## Data model
```python
@dataclass
class Requirement:
    id: str            # R1, R2, ...
    text: str
    keywords: List[str]

@dataclass
class MatrixRow:
    id: str
    requirement: str
    status: str        # "Covered" | "Partial" | "Missing"
    score: float       # 0..1 term-coverage ratio
    evidence: str      # matching response sentence (or "")

@dataclass
class MatrixResult:
    rows: List[MatrixRow]
    summary: Dict[str, float]   # total, covered, partial, missing, compliance_pct
    gaps: List[MatrixRow]       # Missing + Partial, worst first
    gap_summary: str
```

## Extraction — `extract_requirements(rfp_text)`
1. Split into candidate units: sentences (on `.?!` and newlines) **plus** explicit
   list items (lines starting with `-`, `*`, `•`, or `\d+.` / `\d+)`).
2. Keep a unit as a requirement if it either:
   - matches a **modal** regex `\b(shall|must|required to|should|is required)\b`, or
   - is a list item ≥ 4 words (captures listed requirements without modals).
3. Normalise whitespace, drop duplicates (case-insensitive), assign `R1..Rn` in
   order. Derive `keywords` = content words (len ≥ 4, minus stopwords), lowercased.

## Matching — coverage of a requirement in the response
For each requirement:
- Split response into sentences; for each sentence compute
  `overlap = |req.keywords ∩ sentence_words| / |req.keywords|`.
- `score = max(overlap over sentences)`; `evidence` = the best sentence (if score>0).
- Classify: `score ≥ 0.5` → **Covered**; `0.2 ≤ score < 0.5` → **Partial**;
  `score < 0.2` → **Missing**.
Thresholds are module constants (`COVERED_T=0.5`, `PARTIAL_T=0.2`), tunable.

## Summary
- `total`, `covered`, `partial`, `missing` counts.
- `compliance_pct = round(100 * covered / total)` (0 when total = 0).
- `gaps` = Partial + Missing rows sorted by ascending score (worst first).
- `gap_summary`: deterministic sentence (e.g. "3 gaps: 1 missing, 2 partial.");
  replaced by an LLM one-liner only when an online client is passed.

## Exposure
- **API:** `POST /api/v1/compliance/matrix` in `api_server.py` accepts
  `{rfp_text, response_text}`; returns rows + summary + gaps.
- **UI:** a "📋 Compliance" tab in `app_prod.py`: two text areas (RFP, our
  response) → matrix table with status badges, a compliance-% metric, and the gap
  list; logs a `COMPLIANCE_MATRIX` audit entry. The RFP/response may be
  pre-filled from uploaded Knowledge.

## Error boundaries
- Empty RFP → `rows=[]`, `compliance_pct=0`, no exception.
- Empty response → every requirement Missing.
- Non-string inputs coerced to `""`. Matching never divides by zero (empty
  keyword set → score 0 → Missing).

## Test strategy (maps to tasks)
- Extraction: modal sentences + list items captured; duplicates collapsed; IDs
  sequential.
- Matching: exact-term response → Covered; partial overlap → Partial; unrelated →
  Missing; empty response → all Missing.
- Summary: compliance_pct arithmetic; gaps sorted worst-first; determinism.
