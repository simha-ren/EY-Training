# 🎯 Kiro — Spec-Driven Development Framework

Welcome to the **Kiro Spec-Driven Development (SDD)** framework in ProposalForge Pro!

This directory contains structured feature specifications following the AWS Kiro SDD methodology:  
**Requirements → Design → Tasks → Implementation → Quality Gates**.

---

## 📋 Overview

Kiro replaces ad-hoc "vibe coding" with an auditable, transparent development workflow. Each feature is tracked through three phases with explicit approval gates.

### The Three Phases

#### **Phase 1: Requirements Gathering**
- Define user stories and acceptance criteria (EARS notation)
- Document edge cases and behavioral boundaries
- **Quality Gate 1**: Operator verifies all criteria before design begins

**File**: `specs/<feature>/requirements.md`

#### **Phase 2: Technical Design**
- Map requirements to architecture and components
- Define data models, APIs, error handling
- Identify dependencies and constraints
- **Quality Gate 2**: Architecture review before task execution

**File**: `specs/<feature>/design.md`

#### **Phase 3: Task Breakdown & Execution**
- Decompose into granular, parallel-safe tasks
- Define Definition of Done (DoD) for each task
- Execute in dependency-ordered waves
- **Quality Gate 3**: All tasks pass before shipping

**File**: `specs/<feature>/tasks.md`

---

## 🗂️ Directory Structure

```
.kiro/
├── README.md                                 ← You are here
├── config.yaml                               ← Global Kiro configuration
├── IMPLEMENTATION_SUMMARY.md                 ← Feature implementation summary
│
└── specs/
    └── compliance-matrix/                    ← Example feature
        ├── requirements.md                   ← Phase 1: Requirements ✅
        ├── design.md                         ← Phase 2: Design ✅
        └── tasks.md                          ← Phase 3: Tasks ✅
```

---

## ✅ Implemented Features

### 1. **Compliance / Requirements Traceability Matrix**

**Status**: ✅ **COMPLETE & DEPLOYED**

Extract requirements from RFP documents and trace coverage in proposal responses.

- **Phase 1**: Requirements ✅ Approved
- **Phase 2**: Design ✅ Approved
- **Phase 3**: Tasks ✅ 6/6 Completed
- **Implementation**:
  - Core: `src/agents/compliance_matrix.py`
  - API: `POST /api/v1/compliance/matrix`
  - UI: `📋 Compliance` tab in Streamlit
  - Tests: `tests/test_compliance_matrix.py` (100% coverage)

**Quick Start**:
```bash
# See the implementation summary
cat .kiro/IMPLEMENTATION_SUMMARY.md

# Read the specifications
cat .kiro/specs/compliance-matrix/requirements.md
cat .kiro/specs/compliance-matrix/design.md
cat .kiro/specs/compliance-matrix/tasks.md

# Run tests
pytest tests/test_compliance_matrix.py -v
```

---

## 🚀 How to Use Kiro for New Features

### Step 1: Initialize Spec Directory

```bash
mkdir -p .kiro/specs/<feature-name>
```

### Step 2: Write Phase 1 (Requirements)

Create `.kiro/specs/<feature-name>/requirements.md`:

```markdown
# Requirements: <Feature Name>

## Context & Intent
Brief description of the problem being solved.

## Requirements & Behavioral Logic

### Requirement 1: <Req Name>
**User Story:** As a [role], I want [action] so that [benefit].

#### Acceptance Criteria (EARS)
- WHEN [condition], THEN [system behavior].
- IF [condition], THEN [system behavior].
- ...

### Requirement 2: ...
...

## Kiro Quality Gate 1
> Code generation paused. Operator verification:
> - [ ] All user stories align with business goals
> - [ ] Acceptance criteria are testable
> - [ ] Edge cases addressed
>
> Status: ⏳ Awaiting Approval
```

### Step 3: Operator Reviews & Approves Phase 1

Checklist:
- [ ] Are all user stories clear and achievable?
- [ ] Are acceptance criteria testable?
- [ ] Are edge cases explicitly handled?
- [ ] Does the scope align with product goals?

Update `requirements.md`:
```markdown
## Kiro Quality Gate 1
> Status: ✅ APPROVED - Proceed to design
```

### Step 4: Write Phase 2 (Design)

Create `.kiro/specs/<feature-name>/design.md`:

```markdown
# Technical Design: <Feature Name>

## Overview
Architecture and component overview.

## Module Structure
Describe where code will live and how components interact.

## Data Models
Define dataclasses or schemas.

## API/UI Exposure
Document endpoints or UI components.

## Error Boundaries
How the system handles failures.

## Kiro Quality Gate 2
> Status: ⏳ Awaiting Approval
```

### Step 5: Operator Reviews & Approves Phase 2

Checklist:
- [ ] Is the architecture sound?
- [ ] Are dependencies clearly identified?
- [ ] Is error handling comprehensive?
- [ ] Do data models match requirements?

Update `design.md`:
```markdown
## Kiro Quality Gate 2
> Status: ✅ APPROVED - Proceed to tasks
```

### Step 6: Write Phase 3 (Tasks)

Create `.kiro/specs/<feature-name>/tasks.md`:

```markdown
# Task Breakdown: <Feature Name>

## Task 1: [Task Name]
**Assigned**: [Role]
**Effort**: [Hours]
**Dependencies**: [Task IDs or None]

### Description
What needs to be built.

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Definition of Done
- Code merged to main
- Tests passing (≥80% coverage)
- Code review approved

---
## Task 2: ...
...

## Execution Timeline
[Summary of parallel waves and schedule]

## Kiro Quality Gate 3
> Status: ⏳ Awaiting Approval
```

### Step 7: Operator Approves Task Execution

Checklist:
- [ ] All tasks have clear owners
- [ ] Dependencies are correctly ordered
- [ ] DoD criteria are measurable
- [ ] Effort estimates are realistic

Update `tasks.md`:
```markdown
## Kiro Quality Gate 3
> Status: ✅ APPROVED - Execute tasks
```

### Step 8: Execute Tasks

Engineers implement features following task descriptions. Update task status:

```markdown
- [x] **Task 1**: [Task Name]  ✅ PASSED
- [x] **Task 2**: [Task Name]  ✅ PASSED
...

All tasks completed ✅
```

### Step 9: Close Feature

Add to `.kiro/config.yaml`:

```yaml
specs:
  feature-name:
    name: "Feature Display Name"
    phase: 3
    status: "✅ COMPLETE & DEPLOYED"
    phases:
      1_requirements:
        status: "✅ Approved"
      2_design:
        status: "✅ Approved"
      3_tasks:
        status: "✅ COMPLETED"
```

---

## 📊 Quality Gates Checklist

### Gate 1: Requirements Approval

**Sign-off Criteria**:
- [ ] All user stories align with business goals
- [ ] Acceptance criteria are clear and testable
- [ ] Edge cases are explicitly addressed
- [ ] Scope is well-bounded
- [ ] Requirements don't contradict each other

**Document**: Operator signs off in `requirements.md` under "Kiro Quality Gate 1"

### Gate 2: Design Approval

**Sign-off Criteria**:
- [ ] Architecture is sound and scalable
- [ ] Components are well-separated
- [ ] Data models are well-designed
- [ ] Error handling is comprehensive
- [ ] Dependencies are minimal

**Document**: Architecture lead signs off in `design.md` under "Kiro Quality Gate 2"

### Gate 3: Task Execution

**Sign-off Criteria**:
- [ ] All tasks completed
- [ ] All tests passing (≥80% coverage)
- [ ] Code reviewed and approved
- [ ] Performance benchmarks met
- [ ] Audit/compliance logged

**Document**: All tasks checked off in `tasks.md`

---

## 🔄 Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Feature Request / Business Need                             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: Requirements Gathering                             │
│  - Write user stories (EARS notation)                        │
│  - Define acceptance criteria                               │
│  - Document edge cases                                      │
│  File: requirements.md                                       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
         🚪 QUALITY GATE 1
    [Operator Reviews & Approves]
         ✅ Approved ❌ Rejected
                 │
                 ├─ ❌ → Return to Phase 1
                 │
                 ▼ ✅
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: Technical Design                                   │
│  - Define components & architecture                         │
│  - Document data models                                     │
│  - Specify APIs/UI exposure                                 │
│  File: design.md                                             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
         🚪 QUALITY GATE 2
    [Architecture Lead Reviews]
         ✅ Approved ❌ Rejected
                 │
                 ├─ ❌ → Return to Phase 2
                 │
                 ▼ ✅
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: Task Breakdown & Execution                         │
│  - Decompose into granular tasks                            │
│  - Define DoD for each task                                 │
│  - Execute in parallel waves                                │
│  File: tasks.md                                              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
         🚪 QUALITY GATE 3
    [QA & Engineering Verify]
         ✅ All Passed ❌ Some Failed
                 │
                 ├─ ❌ → Fix failures, re-run tests
                 │
                 ▼ ✅
┌─────────────────────────────────────────────────────────────┐
│  FEATURE DEPLOYED ✅                                         │
│  - Merged to main branch                                    │
│  - Tests passing                                            │
│  - In production                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Best Practices

### ✅ DO

- **Be specific**: Use precise language; avoid vague requirements
- **Use EARS notation**: Structures acceptance criteria clearly
- **Document edge cases**: Handle empty inputs, malformed data, etc.
- **Keep tasks small**: Aim for 2–4 hour tasks for parallelization
- **Define DoD clearly**: Make completion measurable
- **Test early**: Write unit tests during task execution
- **Get approval**: Don't skip quality gates

### ❌ DON'T

- **Skip requirements**: Rushing to code leads to rework
- **Vague acceptance criteria**: Ambiguity causes disputes
- **Ignore dependencies**: Parallel execution requires clear ordering
- **Large tasks**: >8 hours → hard to parallelize
- **Incomplete tests**: Aim for ≥80% coverage
- **Approve without review**: Gates exist for a reason

---

## 📚 Example: Compliance Matrix Feature

The `specs/compliance-matrix/` directory contains a **complete, production-ready** example:

```bash
# View Phase 1 requirements
cat specs/compliance-matrix/requirements.md

# View Phase 2 technical design
cat specs/compliance-matrix/design.md

# View Phase 3 task breakdown
cat specs/compliance-matrix/tasks.md

# See implementation summary
cat IMPLEMENTATION_SUMMARY.md

# View Kiro config
cat config.yaml
```

---

## 🔗 References

- [AWS Kiro Documentation](https://aws.amazon.com/builders/) (conceptual framework)
- [ProposalForge Pro Architecture](../docs/architecture.md)
- [Feature Implementation Guide](../docs/FEATURES.md)

---

## ❓ FAQ

**Q: What if requirements change mid-implementation?**  
A: Document the change in `requirements.md`, re-approve Gate 1, and update design/tasks as needed.

**Q: Can I skip quality gates?**  
A: No. Gates ensure code quality and prevent rework. They're fast (1–2 hours).

**Q: What if a task takes longer than estimated?**  
A: Update the task estimate in `tasks.md` and communicate with stakeholders. Mark as in-progress until complete.

**Q: Can I parallelize tasks that share dependencies?**  
A: No, they must execute in sequence. Define dependency chains clearly in tasks.md.

**Q: Where do I store implementation code?**  
A: Follow the structure in `design.md`. Link task implementations to file paths.

---

## 📞 Support

For questions about Kiro or feature specification:

1. Review the [compliance-matrix example](specs/compliance-matrix/)
2. Read the [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
3. Check [ProposalForge Pro architecture](../docs/architecture.md)
4. Reach out to the architecture team

---

**Kiro SDD Framework v1.0**  
*Spec-Driven Development for Auditable, High-Quality Code*

*Last Updated: July 8, 2026*
