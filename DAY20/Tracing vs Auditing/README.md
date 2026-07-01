# Traces (Spans) vs. Audit Logging

Both record "what happened," but they answer **different questions for different people**, and conflating them is a common and costly mistake. This note covers how they relate, how to connect them, and when to reach for each.

---

## 1. What each is actually for

| | **Traces / Spans** | **Audit Logs** |
|---|---|---|
| **Question answered** | *How did the system behave?* | *Who did what, to what, when, from where — and was it allowed?* |
| **Primary consumer** | Engineers, SREs | Security, compliance, auditors, IR |
| **Semantics** | Technical (`POST /roles took 43ms`) | Business-level (`user X granted admin to user Y`) |
| **Layer emitted** | Ambient / automatic (RPC + infra) | Intentional / curated (business logic) |
| **Completeness** | Lossy — heavily **sampled** | **Every** event — no sampling |
| **Retention** | Days → weeks | Months → **years** (SOX, HIPAA, PCI-DSS, GDPR) |
| **Mutability** | Mutable, best-effort export | **Append-only, tamper-evident** |
| **Write path** | Fire-and-forget OK | Often **synchronous / transactional** |
| **Cost of dropping a record** | Inconvenient | **Compliance failure / liability** |

> **Rule of thumb:** if losing the record is merely *inconvenient*, it's a **trace**. If losing the record is a *liability*, it's an **audit log**.

---

## 2. How they relate

The two are produced at **different layers** for **different guarantees**. Tracing is instrumented low (at the RPC/infra boundary); audit events are emitted high (in business logic, exactly when a security-relevant action occurs).

```mermaid
flowchart TB
    subgraph BL["Business-logic layer — intentional & curated"]
        A["grantAdmin(actor, target)"] -->|"security-relevant action"| AUD[["emit AUDIT event"]]
    end
    subgraph INFRA["RPC / infra layer — ambient & automatic"]
        S1["span: POST /roles"] --> S2["span: authz check"]
        S2 --> S3["span: DB write"]
    end
    A -.runs within.-> S1
    AUD -->|store trace_id + span_id| LINK(("correlation\nID"))
    S1 -->|trace_id| LINK
    LINK --> AUDSTORE[("Audit store\nappend-only, years")]
    LINK --> TRACESTORE[("Trace backend\nsampled, days")]
```

The clean way to connect them is a **correlation ID**: stamp the `trace_id` (and `span_id`) into every audit record.

```mermaid
sequenceDiagram
    participant Inv as Investigator
    participant AUD as Audit store
    participant TR as Trace backend

    Inv->>AUD: "Who escalated privileges at 02:14?"
    AUD-->>Inv: actor, target, result + trace_id=abc123
    Note over Inv,TR: pivot on trace_id
    Inv->>TR: show trace abc123
    TR-->>Inv: full cross-service span tree (how it executed)
    Note over Inv: accountability + technical context,<br/>without merging the two systems
```

You get **accountability** (audit) *and* **technical context** (trace) — and you can pivot freely between them.

---

## 3. What NOT to do

Don't make one system do the other's job.

```mermaid
flowchart LR
    T["Traces as an audit trail"] --> TX["❌ sampled = incomplete<br/>❌ short-lived<br/>❌ mutable<br/>❌ technical, not legal meaning"]
    L["Audit logs as a debugger"] --> LX["❌ no timing<br/>❌ no cross-service causal tree<br/>❌ too coarse to find a bottleneck"]
```

**Also distinct from ordinary application logs.** App logs and audit logs often share a pipeline, but app logs are *diagnostic and disposable* while audit logs are *evidentiary*. Treating audit events as "just another log line" is how you end up with sampled, mutable, 7-day-retained records that don't survive a real audit.

```mermaid
flowchart TB
    APP["Application / structured logs<br/><i>diagnostic · disposable</i>"]
    AUDIT["Audit logs<br/><i>evidentiary · non-repudiable</i>"]
    TRACE["Traces / spans<br/><i>behavioral · sampled</i>"]
    APP -. "shared pipeline ≠ shared guarantees" .- AUDIT
```

---

## 4. When to use which

```mermaid
flowchart TD
    Q{"What is the question?"}
    Q -->|"Technical: latency, errors,<br/>flow, bottlenecks"| TRACE["Use TRACING"]
    Q -->|"Accountability or<br/>regulatory obligation"| AUDIT["Use AUDIT LOGGING"]
    Q -->|"Security incident or<br/>high-value transaction"| BOTH["Use BOTH, correlated"]

    TRACE --> TRACEX["latency debugging · error origin<br/>cross-service flow · capacity planning"]
    AUDIT --> AUDITX["authN/authZ events · role & permission changes<br/>privilege escalation · sensitive/PII/financial access<br/>admin & config changes"]
    BOTH --> BOTHX["immutable record of WHAT was done<br/>+ rich trace of HOW it executed"]
```

**Use tracing** when the question is technical — latency debugging, finding where an error originates, understanding flow across microservices, spotting bottlenecks, capacity planning.

**Use audit logging** when the question is about accountability or you have a regulatory obligation — authentication/authorization events, permission and role changes, privilege escalation, access to sensitive/PII/financial data, admin and config changes. Anything that must be non-repudiable and defensible later.

**Use both, correlated**, for security incident response and high-value transactions — the immutable record of *what was done* alongside the rich trace of *how it executed*.

---

## 5. One-line summary

> Tracing tells you **how the machine behaved** and is allowed to forget. Audit logging tells you **who is accountable** and is not allowed to forget. Link them by `trace_id`; never substitute one for the other.
