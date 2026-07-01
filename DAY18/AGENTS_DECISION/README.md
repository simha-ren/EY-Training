> **Single Agent vs Multi-Agent**: In-depth justifications and ASCII architecture diagrams for 4 real-world enterprise scenarios.

---

## 📋 Decision Summary

| # | Domain | System | Verdict | Primary Reason |
|---|--------|--------|---------|----------------|
| 1 | Healthcare | Apollo Diagnostics | **Multi-Agent** (Sequential + Gates) | 4 distinct specialist domains, isolated failure modes |
| 2 | Legal | ContractIQ | **Multi-Agent** (Parallel Fleet + Orchestrator) | 800 docs are embarrassingly parallel; synthesis is a separate concern |
| 3 | E-Commerce | ShopIQ | **Single Agent × 4M** (Batch Queue) | All steps share one user context; parallelism is across users, not within |
| 4 | DevOps | CloudOps Sentinel | **Multi-Agent** (Concurrent + HITL Gate) | Concurrent sub-investigations; gated remediation; 3 different tool surfaces |

---

## 🏥 Scenario 1 — Healthcare / Apollo Diagnostics
### Automated Radiology Report + Care Pathway

#### The Problem
Apollo wants to automate the end-to-end workflow when a chest CT scan arrives:
1. A radiologist-grade model reads the scan and drafts a findings report
2. A clinical-decision-support system cross-checks findings against the patient's medication history for contraindications
3. A scheduling agent books the recommended follow-up (e.g. biopsy, PET scan) in the hospital's EMR
4. A communication agent drafts the GP letter and patient-facing summary

**Constraints tagged:** `4 distinct domains` · `Sequential with gates` · `Different tool access`

---

#### ✅ Decision: Multi-Agent (Sequential Pipeline with Hard Gates)

#### Justification

**Why NOT a single agent?**
- A single agent would need to simultaneously hold: radiology imaging knowledge, pharmacology/contraindication rules, EMR scheduling protocols, and clinical communication standards — these are 4 genuinely distinct knowledge domains that pollute each other in a shared context window.
- Each step has a **completely different tool** (DICOM reader → medication API → EMR write → patient portal). A single agent managing all 4 tool surfaces is a maintenance nightmare and a single point of failure.
- Most critically: **failure modes are isolated and must stay that way.** A scheduling failure should not force a re-run of the expensive radiology model call. In a single-agent loop, a mid-pipeline failure retries everything.

**Why multi-agent with gates?**
- Each agent is a **specialist** — it holds exactly the context it needs, uses exactly the tools it needs, and fails in a contained way.
- Sequential gating is a **hard clinical requirement**: you cannot book a biopsy before the radiology report is verified; you cannot write the GP letter before the follow-up is confirmed. The pipeline must be ordered and gated, not concurrent.
- Gate thresholds (e.g. confidence score from radiology model) can trigger **human-in-the-loop escalation** at the right boundary without disrupting other agents.

---

#### 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    TRIGGER                                   │
│              🩻 Chest CT Scan Arrives                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  AGENT 1 — Radiology Agent                  │
│                                                             │
│  Input : DICOM image                                        │
│  Tool  : Vision model + DICOM reader                        │
│  Output: Findings report + confidence score                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
              ┌─────────▼─────────┐
              │    GATE CHECK     │
              │ confidence ≥ 85%? │
              └─────┬───────┬─────┘
                    │ YES   │ NO
                    │       └──────────► Human radiologist review
                    ▼
┌─────────────────────────────────────────────────────────────┐
│            AGENT 2 — Clinical Decision Support Agent        │
│                                                             │
│  Input : Findings report + patient record ID               │
│  Tool  : Medication history API, contraindication rules DB  │
│  Output: Cleared or flagged recommendations                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              AGENT 3 — Scheduling Agent                     │
│                                                             │
│  Input : Cleared recommendations                           │
│  Tool  : Hospital EMR write API                             │
│  Output: Booking confirmation + appointment details         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│             AGENT 4 — Communication Agent                   │
│                                                             │
│  Input : Findings + recommendations + booking              │
│  Tool  : Document renderer + Patient portal API             │
│  Output: GP letter + patient-facing summary                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
              ✅ Complete Care Pathway Delivered
```

#### Key Design Principles Applied
- **Specialist over generalist**: Each agent has a narrow, well-defined responsibility
- **Gate pattern**: Pipeline only proceeds when the previous step meets a quality threshold
- **Failure isolation**: A scheduling failure doesn't invalidate the radiology findings
- **Human escalation points**: Inserted at confidence-sensitive boundaries

---

## ⚖️ Scenario 2 — Legal / ContractIQ
### M&A Due Diligence on 800 Contracts

#### The Problem
A PE firm uploads 800 supplier and employment contracts ahead of an acquisition. ContractIQ must:
- Extract key obligations and risk clauses from each document (**parallelisable across contracts**)
- Cross-reference extracted clauses against a jurisdiction-specific regulatory checklist
- Identify inter-contract dependencies (e.g. change-of-control clauses that cascade)
- Produce an executive risk summary with a red/amber/green heat map

**Constraints tagged:** `800 docs, parallel` · `Cross-doc synthesis` · `4-hour SLA`

---

#### ✅ Decision: Multi-Agent (Parallel Extraction Fleet + Synthesis Orchestrator)

#### Justification

**Why NOT a single agent?**
- A single agent processing 800 contracts **serially** at ~30s/doc = **6.7 hours** — violates the 4-hour SLA.
- Even with a very large context window, stuffing 800 contracts into one prompt would far exceed token limits and produce degraded extraction quality (lost-in-the-middle problem).
- The two stages — extraction and synthesis — have fundamentally different compute profiles. Extraction is stateless and parallelisable; synthesis requires global state (all extracted clauses simultaneously). Conflating them in one agent means the synthesis step holds 800 documents in context, which is impractical.

**Why multi-agent with two phases?**
- **Phase 1 (Parallel Fleet)**: 800 independent worker agents — one per contract. Each is stateless, processes its document, emits a structured JSON of clauses. These run concurrently on a job queue. With 100 concurrent workers, 800 docs completes in ~4 minutes of wall-clock time.
- **Phase 2 (Synthesis Orchestrator)**: A single orchestrator receives all 800 JSON extractions, runs cross-reference logic against the regulatory checklist, detects dependency cascades, and produces the heatmap. This step **intentionally** has global state — it needs to see everything to find inter-contract patterns.
- The two-phase architecture precisely matches the problem statement: *"Documents are independent at extraction stage but interdependent at the synthesis stage."*

---

#### 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    TRIGGER                                   │
│           📂  800 Contracts Uploaded by PE Firm              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│            ORCHESTRATOR — Dispatch Queue                    │
│                                                             │
│  Shards 800 contracts → pushes jobs to worker queue         │
│  Tracks completion, handles retries on worker failure       │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌───────────┐
│  W1  │  │  W2  │  │  W3  │  │  W4  │  │  ···×796  │
│      │  │      │  │      │  │      │  │           │
│Extract  │Extract  │Extract  │Extract  │  Extract  │
│clauses  │clauses  │clauses  │clauses  │  clauses  │
└──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └────┬──────┘
   │          │          │          │           │
   └──────────┴──────────┴──────────┴───────────┘
                         │
                         │  fan-in: all 800 JSON extractions
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           SYNTHESIS ORCHESTRATOR                            │
│                                                             │
│  ┌───────────────────┐  ┌─────────────────────────────┐    │
│  │ Regulatory        │  │ Dependency Graph Builder     │    │
│  │ Checklist Engine  │  │ (change-of-control cascade)  │    │
│  └─────────┬─────────┘  └──────────────┬──────────────┘    │
│            └────────────────┬───────────┘                   │
│                             ▼                               │
│              RAG Heatmap Generator (R/A/G)                  │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
              📊 Executive Risk Summary Delivered
                   within 4-hour SLA ✅
```

#### Performance Model
```
Serial (single agent):   800 docs × 30s = 6.7 hours  ❌ SLA breach
Parallel (100 workers):  800 docs / 100 = 8 batches × 30s = 4 min  ✅
+ Synthesis overhead:    ~30 min
Total wall-clock time:   ~35 min  ✅✅
```

---

## 🛒 Scenario 3 — E-Commerce / ShopIQ
### Personalised Product Recommendation Email (4M users)

#### The Problem
ShopIQ runs a nightly batch job to send personalised recommendation emails to **4 million users**. For each user:
- Pull their 6-month purchase and browse history
- Run a collaborative-filtering model to get top-10 candidates
- Apply business rules (exclude out-of-stock, exclude recently-purchased)
- Write a short personalised intro paragraph
- Assemble the email HTML

**Constraints tagged:** `Batch: 4M users` · `Shared user context` · `< 3s per user`

---

#### ✅ Decision: Single Agent Per User (Massively Parallel Batch Workers)

#### Justification

**Why NOT multi-agent per user?**
- All 5 sub-tasks (fetch history → filter → rules → copywriting → assembly) share **exactly one object**: the user context. There is zero benefit to passing this between sub-agents — each handoff adds serialisation, network, and coordination latency.
- With a <3s SLA per user, every millisecond of inter-agent overhead is multiplied across 4M users. Sub-agent orchestration typically adds 200–500ms per hop; with 5 hops, that's 1–2.5 seconds of pure overhead, potentially violating the SLA.
- The tasks are not independent enough to run concurrently within a single user — step 2 needs the output of step 1, step 3 needs the output of step 2, etc. Concurrent sub-agents would still need to serialise.

**Why single agent per user?**
- One agent holds the full user context and executes all 5 steps as a simple sequential pipeline. No coordination overhead. Minimal latency.
- The required parallelism is **across users, not within a user's pipeline**. This is achieved by running 4M single-agent jobs concurrently on a distributed queue.
- This pattern is extremely well-understood, operationally simple, and horizontally scalable.

---

#### 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    TRIGGER                                   │
│           ⚙️  Nightly Batch Job — 23:00 UTC                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 DISTRIBUTED JOB QUEUE                       │
│              4,000,000 user jobs enqueued                   │
│         (e.g. Celery + Redis / AWS SQS / Kafka)             │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────────────────────────────────────────────┐
│         SINGLE AGENT WORKER (per user)       │  × 4,000,000
│                                              │
│  ctx = load_user_context(user_id)            │
│                                              │
│  ① history   = fetch_6mo_history(ctx)        │
│       ↓                                      │
│  ② candidates = collab_filter(history)       │
│       ↓                                      │
│  ③ candidates = apply_rules(candidates, ctx) │
│     - exclude out-of-stock                   │
│     - exclude recently-purchased             │
│       ↓                                      │
│  ④ intro = llm_write_intro(ctx, candidates)  │
│       ↓                                      │
│  ⑤ email_html = assemble_email(intro,        │
│                                candidates)   │
│                                              │
│  send(ctx.email, email_html)                 │
│                         ⏱ < 3s total         │
└──────────────────────────────────────────────┘
                        │
                        ▼
         📧 4,000,000 emails dispatched ✅

─────────────────────────────────────────────
WHY THIS IS NOT MULTI-AGENT PER USER:

  ctx ──► Agent A ──► ctx ──► Agent B ──► ctx ──► ...
                ↑                   ↑
         serialisation         network hop
         overhead              overhead
         (~100ms each)         (~100ms each)
                    = 400-500ms wasted per user
                    = 4M × 500ms = 555 hours wasted
─────────────────────────────────────────────
```

#### The Core Insight

> The word "parallel" in this scenario means *parallel across users*, not *parallel within a single user's pipeline*. A multi-agent architecture would solve the wrong problem.

---

## 🔧 Scenario 4 — DevOps / CloudOps Sentinel
### Incident Triage & Auto-Remediation

#### The Problem
An alert fires: p99 API latency has spiked to 4.2s on the payments service. CloudOps Sentinel must:
- **(a)** Query metrics (Datadog) to identify which pods are degraded
- **(b)** Check recent deployment logs (GitHub Actions) for a root cause
- **(c)** Query the DB slow-query log (AWS RDS)
- **(d)** If confident, execute a rollback or pod restart via kubectl
- **(e)** Post a structured RCA to the #incidents Slack channel

**Rules:** Steps (a)–(c) can run concurrently. (d) requires human approval if confidence < 80%. (e) always runs last.

**Constraints tagged:** `Concurrent sub-investigations` · `Human-in-the-loop gate` · `Different tool surfaces`

---

#### ✅ Decision: Multi-Agent (Concurrent Investigators + HITL Gate + Sequential Closer)

#### Justification

**Why NOT a single agent?**
- A single agent running (a), (b), (c) sequentially would take 3× longer — in a live production incident, MTTD (Mean Time To Detect) is critical.
- Steps (a), (b), (c) use **completely different tool surfaces** (Datadog API, GitHub API, AWS RDS) with different authentication, rate limits, and response schemas. A single agent juggling all 3 in one context accumulates noise and is harder to debug when one integration fails.
- The human-in-the-loop gate on (d) is most cleanly expressed as a **decision boundary between agents**, not as a conditional branch inside a single agent's reasoning loop.

**Why multi-agent?**
- **(a), (b), (c) as concurrent agents**: Launch simultaneously, each owns its tool surface. The orchestrator collects their findings in parallel and synthesises a confidence score. This is the canonical use case for concurrent multi-agent: independent sub-tasks with no dependencies between them.
- **(d) as a gated remediation agent**: The orchestrator checks confidence. ≥80% → auto-trigger. <80% → send approval request to on-call engineer, await response, then trigger. This gate is a first-class architectural concern, not a code comment.
- **(e) as a notification agent**: Always runs last regardless of (d)'s outcome — even if remediation was blocked, the RCA still posts to Slack. This sequencing guarantee is cleanest as a separate, always-triggered final step.

---

#### 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    TRIGGER                                   │
│   🚨 Alert: p99 latency = 4.2s on payments-service          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│               ORCHESTRATOR — Incident Manager               │
│         Receives alert, spawns concurrent investigators     │
└──────┬───────────────┬───────────────┬──────────────────────┘
       │               │               │
       │  spawn        │  spawn        │  spawn
       ▼               ▼               ▼
┌────────────┐  ┌─────────────┐  ┌────────────────┐
│  AGENT (a) │  │  AGENT (b)  │  │   AGENT (c)    │
│  Metrics   │  │  Deploy     │  │   DB Agent     │
│  Agent     │  │  Agent      │  │                │
│            │  │             │  │                │
│ Tool:      │  │ Tool:       │  │ Tool:          │
│ Datadog    │  │ GitHub      │  │ AWS RDS        │
│ metrics    │  │ Actions     │  │ slow-query     │
│ API        │  │ API         │  │ log API        │
│            │  │             │  │                │
│ Output:    │  │ Output:     │  │ Output:        │
│ Degraded   │  │ Recent      │  │ Slow queries   │
│ pods list  │  │ deployments │  │ & lock waits   │
└─────┬──────┘  └──────┬──────┘  └───────┬────────┘
      │                │                  │
      └────────────────┴──────────────────┘
                       │
                       │  all 3 complete (async fan-in)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           ORCHESTRATOR — Root Cause Synthesiser             │
│                                                             │
│  Correlates: pod degradation + recent deploys + slow SQL    │
│  Produces: likely root cause + confidence score (0–100%)    │
└───────────────────────┬─────────────────────────────────────┘
                        │
              ┌─────────▼──────────┐
              │  HUMAN-IN-THE-LOOP │
              │      GATE          │
              │                    │
              │  confidence ≥ 80%? │
              └───┬────────────┬───┘
                  │ YES        │ NO
                  │            │
                  │            ▼
                  │   ┌───────────────────┐
                  │   │ PagerDuty alert   │
                  │   │ to on-call eng.   │
                  │   │ Awaiting approval │
                  │   └────────┬──────────┘
                  │            │ approved
                  └────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           AGENT (d) — Remediation Agent                     │
│                                                             │
│  Tool: kubectl                                              │
│  Action: rollback deployment OR restart degraded pods       │
│  Output: remediation result (success/failure + diff)        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │  always runs, regardless of (d) outcome
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           AGENT (e) — Notification Agent                    │
│                                                             │
│  Tool: Slack API → #incidents channel                       │
│  Output: Structured RCA post                                │
│    • Alert summary                                          │
│    • Findings from (a), (b), (c)                           │
│    • Root cause hypothesis                                  │
│    • Remediation action taken (or pending approval)         │
│    • Timeline                                               │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
              ✅ Incident Handled & Documented
```

## 🧠 Architecture Decision Framework

Use this decision tree when choosing between single and multi-agent for a new scenario:

```
START
  │
  ├─► Are sub-tasks using DIFFERENT tool surfaces or knowledge domains?
  │     YES ──► Strong signal for multi-agent (specialist agents)
  │     NO  ──► Continue ▼
  │
  ├─► Do sub-tasks share the SAME context object and have no parallelism within a single unit?
  │     YES ──► Single agent (avoid coordination overhead)
  │     NO  ──► Continue ▼
  │
  ├─► Is there a VOLUME problem that requires parallel processing?
  │     YES (independent units) ──► Single agent × N workers (batch queue)
  │     YES (within one unit)   ──► Multi-agent with concurrent branches
  │     NO  ──► Continue ▼
  │
  ├─► Is there a HUMAN GATE or APPROVAL STEP mid-pipeline?
  │     YES ──► Multi-agent (gate is a first-class boundary between agents)
  │     NO  ──► Continue ▼
  │
  └─► Are FAILURE MODES isolated and must not cascade?
        YES ──► Multi-agent (failure in one agent doesn't retry others)
        NO  ──► Single agent is likely fine
```

---
