# Kiro SDD — Quick Reference Card

## 🎯 Three Phases at a Glance

| Phase | File | Owner | Duration | Output |
|-------|------|-------|----------|--------|
| **1. Requirements** | `requirements.md` | Product/Engineering | 2–4 hrs | User stories + acceptance criteria |
| **2. Design** | `design.md` | Architecture | 2–4 hrs | Components + data models + APIs |
| **3. Tasks** | `tasks.md` | Engineering | 1–2 hrs | Task breakdown + parallel waves |

---

## ✅ Quality Gates Template

### Gate 1: Requirements
```markdown
## Kiro Quality Gate 1
> Operator Verification Checklist:
> - [ ] All user stories align with business goals
> - [ ] Acceptance criteria are testable
> - [ ] Edge cases addressed
> 
> Status: ✅ APPROVED — Proceed to design
```

### Gate 2: Design
```markdown
## Kiro Quality Gate 2
> Architecture Review Checklist:
> - [ ] Components well-separated
> - [ ] Data models well-designed
> - [ ] Error handling comprehensive
> 
> Status: ✅ APPROVED — Proceed to tasks
```

### Gate 3: Tasks
```markdown
## Kiro Quality Gate 3
> Execution Verification:
> - [ ] All tasks completed
> - [ ] Tests passing (≥80% coverage)
> - [ ] Code reviewed
> 
> Status: ✅ COMPLETE — Feature deployed
```

---

## 📝 EARS Notation (Acceptance Criteria)

**EARS** = Easy Approach to Requirements Syntax

### Structure
```
WHEN   [condition]    THEN [system behavior]
IF     [condition]    THEN [system behavior]
GIVEN  [context]      WHEN [action]  THEN [outcome]
```

### Example
```
WHEN a blog post has an 'updated_at' field,
THEN the system SHALL display "Last Updated: [date]".

IF the 'updated_at' date equals the 'date' field,
THEN the system SHALL suppress the update display.

WHEN the 'updated_at' field is malformed,
THEN the system SHALL log a warning and default to 'date'.
```

---

## 🗂️ Feature Directory Structure

```
.kiro/
├── README.md                      ← Overview & workflow guide
├── QUICK_REFERENCE.md             ← This file
├── config.yaml                    ← Global Kiro configuration
├── IMPLEMENTATION_SUMMARY.md      ← Feature summary (post-launch)
│
└── specs/
    └── <feature-name>/            ← One per feature
        ├── requirements.md        ← Phase 1: User stories + criteria
        ├── design.md              ← Phase 2: Architecture + schemas
        └── tasks.md               ← Phase 3: Task breakdown
```

---

## 🚀 New Feature Workflow

### Step 1: Create Directory
```bash
mkdir -p .kiro/specs/my-feature
```

### Step 2: Write Phase 1 (Requirements)
```bash
cat > .kiro/specs/my-feature/requirements.md << 'EOF'
# Requirements: My Feature

## Context & Intent
[Problem description]

## Requirements & Behavioral Logic

### Requirement 1: [Name]
**User Story:** As a [role], I want [action] so that [benefit].

#### Acceptance Criteria (EARS)
- WHEN [condition], THEN [behavior].
- IF [condition], THEN [behavior].

...

## Kiro Quality Gate 1
> Status: ⏳ Awaiting Approval
EOF
```

### Step 3: Get Phase 1 Approval
Operator reviews and updates:
```markdown
## Kiro Quality Gate 1
> Status: ✅ APPROVED - Proceed to design
```

### Step 4: Write Phase 2 (Design)
```bash
cat > .kiro/specs/my-feature/design.md << 'EOF'
# Technical Design: My Feature

## Architecture
[Component overview]

## Data Models
[Dataclasses/schemas]

## API/UI Exposure
[Endpoints or UI components]

## Error Boundaries
[Failure modes]

...

## Kiro Quality Gate 2
> Status: ⏳ Awaiting Approval
EOF
```

### Step 5: Get Phase 2 Approval
Architecture lead reviews and approves.

### Step 6: Write Phase 3 (Tasks)
```bash
cat > .kiro/specs/my-feature/tasks.md << 'EOF'
# Task Breakdown: My Feature

## Task 1: [Task Name]
**Assigned**: [Role]
**Effort**: [Hours]
**Dependencies**: [Task IDs or None]

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Definition of Done
- Code merged to main
- Tests passing (≥80% coverage)
- Code review approved

...

## Kiro Quality Gate 3
> Status: ⏳ Awaiting Approval
EOF
```

### Step 7: Get Phase 3 Approval & Execute
All tasks marked complete:
```markdown
- [x] Task 1: [Name] ✅
- [x] Task 2: [Name] ✅

All tasks completed ✅
```

### Step 8: Post-Launch Summary (Optional)
```bash
cat > .kiro/IMPLEMENTATION_SUMMARY.md << 'EOF'
# Implementation Summary: My Feature

**Status**: ✅ COMPLETE & DEPLOYED
**Date**: [Date]
**Phase**: 3 of 3

[Feature overview, metrics, file locations, usage examples]
EOF
```

---

## 📋 Definition of Done (DoD) Checklist

Every task must satisfy:

- [ ] **Code Complete**: All acceptance criteria implemented
- [ ] **Tests Written**: ≥80% coverage (unit + integration)
- [ ] **Code Review**: Approved by 1–2 reviewers
- [ ] **Documentation**: Comments + docstrings + README updated
- [ ] **Performance**: Meets benchmarks (if applicable)
- [ ] **Error Handling**: Graceful failures, logging
- [ ] **Merged to Main**: No local branches
- [ ] **Audit Trail**: Logging/tracing (if applicable)

---

## 🧠 Task Decomposition Tips

### Good Task Characteristics
- **2–4 hour estimate**: Parallelizable, verifiable
- **Single responsibility**: One domain/component
- **Clear DoD**: Measurable, testable outcomes
- **Minimal dependencies**: Can run in parallel
- **Isolated tests**: Doesn't break other tests

### Bad Task Characteristics
- **8+ hour estimate**: Too large to parallelize
- **Vague scope**: "Implement feature X"
- **No DoD**: "Done when it feels done"
- **Tangled dependencies**: Sequential only
- **Integration tests only**: Can't verify in isolation

### Example: Good Task
```markdown
## Task 2: Email validation utility

**Assigned**: Backend Engineers
**Effort**: 2 hours
**Dependencies**: Task 1

### Description
Implement email validation regex + unit tests.

### Acceptance Criteria
- [ ] Regex matches valid email formats
- [ ] Rejects invalid formats
- [ ] Handles edge cases (empty, spaces, etc.)

### Definition of Done
- src/common/validators.py::validate_email() implemented
- tests/test_validators.py: 6 tests passing (100% coverage)
- Code review approved
- Merged to main
```

---

## 📊 Parallel Execution Waves

Structure tasks in **dependency-ordered waves**:

```
Wave 1 (t=0)
├── Task 1: Extract requirements    (no deps)
├── Task 2: Design schema           (no deps)
└── Task 3: Write test fixtures     (no deps)
    [All run in parallel]

Wave 2 (t+3h)
├── Task 4: API endpoint     (depends on Task 1)
├── Task 5: UI component     (depends on Task 1)
└── Task 6: Data validator   (depends on Task 2)
    [All run in parallel, wait for Wave 1]

Wave 3 (t+5h)
└── Task 7: E2E integration test    (depends on Tasks 4, 5, 6)
    [Sequential, all previous tasks done]
```

---

## ✨ Example Output

### Phase 1: Requirements Approved ✅
```
Requirements: Compliance Matrix Feature
├── User Story 1: Extract requirements from RFP
├── User Story 2: Trace coverage in response
├── User Story 3: Generate compliance % + gaps
├── Edge cases: Empty RFP, malformed input
├── Acceptance criteria: 15 EARS statements
└── 🚪 Gate 1: ✅ APPROVED by engineering team
```

### Phase 2: Design Approved ✅
```
Design: Compliance Matrix Feature
├── Modules: src/agents/compliance_matrix.py
├── Data models: Requirement, MatrixRow, MatrixResult
├── API: POST /api/v1/compliance/matrix
├── UI: 📋 Compliance tab in Streamlit
├── Tests: Extraction, matching, summary building
└── 🚪 Gate 2: ✅ APPROVED by architecture team
```

### Phase 3: Tasks Completed ✅
```
Tasks: Compliance Matrix Feature
├── Task 1: Extract requirements    ✅ Done
├── Task 2: Coverage classifier     ✅ Done
├── Task 3: Build matrix            ✅ Done
├── Task 4: API endpoint            ✅ Done
├── Task 5: UI tab + audit          ✅ Done
├── Task 6: Tests                   ✅ Done
├── All tests passing: 6/6 ✅
└── 🚪 Gate 3: ✅ COMPLETE - Feature deployed
```

---

## 🔗 Key Files

| File | Purpose |
|------|---------|
| `.kiro/README.md` | Full framework guide |
| `.kiro/QUICK_REFERENCE.md` | This file |
| `.kiro/config.yaml` | Global Kiro configuration |
| `.kiro/specs/<feature>/*` | Feature specifications |
| `docs/architecture.md` | System design |
| `docs/FEATURES.md` | All features overview |

---

## 📞 Quick Help

**Q: Where do I start for a new feature?**  
A: Create `.kiro/specs/my-feature/` and write `requirements.md`

**Q: How do I know when to move to the next phase?**  
A: Wait for quality gate approval from stakeholders

**Q: Can I parallelize all tasks?**  
A: No, only tasks with no dependencies. Define dependency chains in `tasks.md`

**Q: What if a requirement changes after Gate 1?**  
A: Document it in `requirements.md`, re-approve Gate 1, update downstream phases

**Q: How much detail in acceptance criteria?**  
A: Enough for code review to verify completion. Use EARS notation.

---

## 🎓 Learning Path

1. **Read** `.kiro/README.md` (full guide)
2. **Study** `.kiro/specs/compliance-matrix/` (complete example)
3. **Review** `.kiro/IMPLEMENTATION_SUMMARY.md` (post-launch summary)
4. **Create** your first feature spec following the pattern

---

**Kiro SDD — Spec-Driven Development**  
*Quality Gates | Auditable Code | Zero Drift*

*Reference Card v1.0 | Last Updated: July 8, 2026*
