# LLM Observability & Guardrails Architecture

## System Overview

This document describes a production-ready, multi-agent LLM pipeline enhanced with comprehensive observability, safety guardrails, auditing, and resilience mechanisms. The system transforms a naive three-agent pipeline (Researcher → Summarizer → Notifier) into a robust, observable, and trustworthy system.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INPUT GUARDRAILS LAYER                                │
│          Required fields • Prompt injection • Topic scope validation        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│   RESEARCHER AGENT   │ →│  SUMMARIZER AGENT    │ →│   NOTIFIER AGENT     │
│  Enriches lead with  │  │ Summarizes lead for  │  │ Generates outreach   │
│   pain point         │  │  sales rep           │  │     message          │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      OUTPUT GUARDRAILS LAYER                               │
│              PII detection • Redaction • Safe logging                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ OBSERVABILITY    │  │  ACCOUNTABILITY      │  │   RESILIENCE         │
│ ───────────────  │  │  ──────────────────  │  │   ──────────────     │
│ • Logging        │  │  • Audit Log         │  │   • Rate Limiting    │
│ • Tracing        │  │  • Hash-Chained      │  │   • Retries          │
│ • Telemetry      │  │  • Immutable Record  │  │   • Cost Ceiling     │
│                  │  │  • LLM-as-Judge      │  │                      │
└──────────────────┘  └──────────────────────┘  └──────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│              OBSERVABILITY DASHBOARD & METRICS                              │
│  Leads • LLM calls • Cost • Latency • Quality • Guardrail blocks • Audit   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Input Guardrails Layer

**Purpose:** Validate and sanitize incoming data before it reaches any LLM.

#### Components:
- **Required Fields Validation** — Ensures all necessary lead data is present
- **Prompt Injection Detection** — Identifies patterns indicative of prompt injection attacks
- **Topic Scope Validation** — Flags inputs that might steer the LLM off-topic

#### Key Mechanism:
```python
GuardResult = namedtuple('GuardResult', ['allowed', 'rule', 'reason', 'severity'])
```

Each guardrail returns a structured result containing a decision, triggered rule name, explanation, and severity level. Violations are logged and the request is blocked.

---

### 2. Core LLM Pipeline

The three-stage pipeline processes leads through specialized agents.

#### Researcher Agent
- **Input:** Lead data (company, contact info, etc.)
- **Output:** Enriched lead with likely pain point
- **Purpose:** Provide context and background for downstream processing

#### Summarizer Agent
- **Input:** Enriched lead data
- **Output:** Concise summary optimized for sales representatives
- **Purpose:** Create actionable insights from enriched lead

#### Notifier Agent
- **Input:** Lead summary
- **Output:** One-line outreach message
- **Purpose:** Generate personalized, compelling first contact message

---

### 3. Output Guardrails Layer

**Purpose:** Prevent sensitive data leakage and ensure compliance before data leaves the system.

#### Components:

##### PII Detection & Redaction
Scans all outputs for personally identifiable information:
- **Email addresses** — Pattern: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`
- **Phone numbers** — Pattern: `(?:\+?1[-.]?)?\d{3}[-.]?\d{3}[-.]?\d{4}`
- **Names** — Pattern: `\b[A-Z][a-z]+ [A-Z][a-z]+\b`
- **Postal addresses** — Pattern: Multi-line street/city/state/ZIP
- **National IDs** — Pattern: SSN, passport, license numbers

##### Redaction Strategy
Detected PII is replaced with generic tokens (e.g., `<EMAIL_1>`, `<PHONE_2>`). A **re-identification map** is maintained separately and kept secure for authorized recovery.

##### Key Metrics:
- **Precision:** Ratio of correctly identified PII to all positive detections
- **Recall:** Ratio of correctly identified PII to all actual PII
- **F1-Score:** Harmonic mean balancing precision and recall

---

### 4. Observability Layer

**Purpose:** Provide complete visibility into system behavior at every stage.

#### 4.1 Structured Logging

**Key Component:** `log_event(level, event_name, **fields)`

Instead of unstructured `print()` statements, all events are logged as JSON objects:

```json
{
  "ts": "2026-01-15T10:30:45.123Z",
  "level": "INFO",
  "event": "llm.call",
  "model": "claude-haiku-4-5-20251001",
  "input_tokens": 125,
  "output_tokens": 42,
  "cost_usd": 0.000086,
  "latency_ms": 450,
  "stop_reason": "end_turn"
}
```

**Benefits:**
- Machine-readable for automated parsing
- Easily aggregated and filtered by log shippers (e.g., Datadog, CloudWatch)
- Structured fields enable fine-grained analysis

**Storage:** `LOG_BUFFER` (in-memory list, can be persisted to disk)

---

#### 4.2 Distributed Tracing (OpenTelemetry)

**Purpose:** Overcome the flat nature of logs by building a hierarchical view of request execution.

**Key Concepts:**

- **Trace:** Represents an entire end-to-end request (e.g., processing a single lead)
- **Span:** A unit of work within a trace (e.g., one agent's operation, a single LLM call)
- **Parent-Child Relationship:** Spans form a tree showing the call hierarchy
- **Span Attributes:** Duration, timestamps, tags, and custom metadata

**OpenTelemetry Components:**
```python
TracerProvider()           # Manages trace creation
OTLPTraceExporter()        # Exports traces to Jaeger or other backends
SpanContext               # Carries trace ID and parent span ID
```

**Example Trace Structure:**
```
Trace: process_lead_L-001
├── Span: input_validation (0-50ms)
├── Span: researcher_agent (50-250ms)
│   └── Span: llm.call (researcher) (50-240ms)
├── Span: summarizer_agent (250-450ms)
│   └── Span: llm.call (summarizer) (250-440ms)
├── Span: notifier_agent (450-600ms)
│   └── Span: llm.call (notifier) (450-590ms)
└── Span: output_guardrails (600-610ms)
```

**Integration:** Traces are exported to Jaeger (via `localhost:4317` by default) for visualization and analysis.

---

#### 4.3 LLM Call Telemetry

**Purpose:** Capture detailed metrics about every LLM invocation for cost, performance, and usage analysis.

**Data Captured:**
```python
LLMResult = namedtuple('LLMResult', [
    'model',                # Model identifier
    'input_tokens',         # Tokens consumed from input
    'output_tokens',        # Tokens generated
    'cost_usd',            # Monetary cost of the call
    'latency_ms',          # End-to-end latency
    'stop_reason',         # Why the model stopped (end_turn, max_tokens, etc.)
    'retries',             # Number of retries attempted
])
```

**Storage:** `LLM_CALLS` ledger (flat list for easy aggregation)

**Cost Calculation:**
```python
cost_usd = (input_tokens * INPUT_PRICE_PER_M) / 1_000_000 + \
           (output_tokens * OUTPUT_PRICE_PER_M) / 1_000_000
```

---

### 5. Accountability Layer

**Purpose:** Maintain an immutable, auditable record of all LLM interactions for compliance and governance.

#### 5.1 Hash-Chained Audit Log

**Concept:** An append-only log where each record cryptographically links to the previous one.

```python
AUDIT_LOG = [
    {
        'prompt': 'Redacted prompt text...',
        'response': 'Redacted response text...',
        'timestamp': '2026-01-15T10:30:45.123Z',
        'hash': 'sha256_hash_of_this_record',
        'prev_hash': 'sha256_hash_of_previous_record',
    },
    ...
]
```

**Integrity Verification:**
1. Compute hash of record N: `hash_n = SHA256(prompt_n + response_n + timestamp_n + prev_hash_n)`
2. Verify `hash_n` matches stored hash
3. Verify `prev_hash_n` matches `hash_{n-1}` from previous record
4. If any mismatch, the chain is broken and tampering is detected

**Key Property:** Tampering with any record breaks the integrity of all subsequent records, making detection unavoidable.

---

#### 5.2 Audit Log Persistence

**Purpose:** Preserve the audit trail across system restarts and sessions.

**Format:** JSON Lines (one record per line)
```
{"prompt": "...", "response": "...", "hash": "...", "prev_hash": "..."}
{"prompt": "...", "response": "...", "hash": "...", "prev_hash": "..."}
```

**Workflow:**
1. `save_audit_log_to_file()` — Write `AUDIT_LOG` to `audit_log.jsonl`
2. `load_audit_log_from_file()` — Read from file and verify hash chain

---

### 6. Feedback Loop & Continuous Improvement

**Purpose:** Drive iterative refinement of pipeline output quality.

#### 6.1 LLM-as-Judge

**Concept:** Use an LLM to evaluate the quality of generated summaries.

**Evaluation Metrics:**
- **Groundedness** — How well does the summary stay faithful to source data? (1-5 scale)
- **Usefulness** — How actionable is the summary for a sales representative? (1-5 scale)

**Judge Prompt:**
```
Rate this lead summary for groundedness and usefulness (1-5 each).
Groundedness: Only assign a 4 or 5 if key facts are *explicitly* mentioned in the source.
Usefulness: Consider if the summary provides actionable insights for a sales rep.

Return JSON only: {"groundedness": N, "usefulness": N}

SOURCE: {source}
SUMMARY: {summary}
```

#### 6.2 Calibration Against Human Labels

**Workflow:**
1. Generate summaries using the pipeline
2. Judge evaluates each summary
3. Compare judge scores against human labels
4. Measure agreement: average difference in scores
5. If disagreement is high, refine the judge's prompt

**Calibration Metrics:**
```
Average difference in Groundedness: 1.00
Average difference in Usefulness: 0.50
```

**Interpretation:** If the LLM consistently overestimates 'groundedness', make the prompt more stringent about requiring explicit mentions from the source.

---

### 7. Resilience Layer

**Purpose:** Ensure the system gracefully handles failures, rate limits, and budget constraints.

#### 7.1 Token Bucket Rate Limiting

**Concept:** A sliding window that allows a burst of requests but throttles sustained load.

**Implementation:**
```python
class TokenBucket:
    def __init__(self, capacity, refill_rate_per_second):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate_per_second
        self.last_refill = time.time()
    
    def try_acquire(self, tokens=1):
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
```

**Configuration Example:**
- Capacity: 10 requests
- Refill rate: 2 requests/second
- Allows burst of 10, then sustained rate of 2/sec

---

#### 7.2 Exponential Backoff Retries

**Purpose:** Gracefully handle transient failures (network timeouts, temporary rate limits).

**Strategy:**
```python
retry_delay = base_delay * (backoff_factor ** retry_count) + jitter
```

**Example:**
- Base delay: 1 second
- Backoff factor: 2
- Max retries: 3
- Jitter: ±10% random

**Sequence:**
1. First attempt (immediate)
2. Rate limit error → wait 1s, retry
3. Another error → wait 2s, retry
4. Another error → wait 4s, retry
5. Still failing → give up, record failure

**Captured Metric:** Retry count is included in `LLMResult` for analysis.

---

#### 7.3 Cost Ceiling & Budget Enforcement

**Purpose:** Prevent runaway costs and enforce spending limits.

**Mechanism:**
```python
GLOBAL_BUDGET_USD = 0.0005  # e.g., $0.0005 per batch
CUMULATIVE_COST_USD = 0.0   # Running total

def instrumented_call(prompt):
    estimated_cost = estimate_cost(prompt)
    if CUMULATIVE_COST_USD + estimated_cost > GLOBAL_BUDGET_USD:
        raise BudgetExceededError(
            f"Cost ${estimated_cost} would exceed budget. "
            f"Current: ${CUMULATIVE_COST_USD}, Limit: ${GLOBAL_BUDGET_USD}"
        )
    result = call_claude(prompt)
    CUMULATIVE_COST_USD += result.cost_usd
    return result
```

**Behavior:**
- Before each LLM call, check if the call would exceed budget
- If yes, raise `BudgetExceededError` and halt processing
- Log the budget exceeded event
- Return `budget_exceeded` status for affected leads

**Example Output:**
```
Cost ceiling set to: $0.0005
Processing leads...

Lead L-001: ok ✓
Lead L-002: budget_exceeded (cost $0.000645 > remaining $0.000414)

Final batch cost: $0.000086
```

---

### 8. Observability Dashboard

**Purpose:** Aggregate telemetry and provide a consolidated view of system health and performance.

#### Dashboard Metrics:

| Metric | Source | Purpose |
|--------|--------|---------|
| Leads processed | `run_lead()` results | Throughput measurement |
| Blocked by guardrail | Failed guardrail checks | Safety monitoring |
| LLM calls | `LLM_CALLS` ledger | Usage tracking |
| Total cost (USD) | Sum of `cost_usd` in `LLM_CALLS` | Budget tracking |
| Avg latency (ms) | Mean of `latency_ms` in `LLM_CALLS` | Performance monitoring |
| Guardrail blocks | Triggered rules list | Safety event tracking |
| Avg quality scores | `judge_output()` results | Quality trending |
| Audit chain status | `verify_chain()` result | Data integrity check |

#### Example Dashboard Output:
```
============================================
 OBSERVABILITY DASHBOARD
============================================
 leads processed      : 3
 blocked by guardrail : 1
 llm calls            : 12
 total cost (usd)     : 0.005374
 avg latency (ms)     : 450.2
 guardrail blocks     : 3  ['prompt_injection', 'prompt_injection', 'prompt_injection']
 avg quality          : {'groundedness': 3.0, 'usefulness': 3.0}
 audit records        : 9 | chain valid: True
============================================
```

---

## Data Flow

### Happy Path (Lead Processing)

```
1. INPUT VALIDATION
   ↓ (passes guardrails)
   
2. RESEARCHER AGENT
   ├─ LLM call → Enriched lead
   ├─ Telemetry logged → LLM_CALLS
   └─ Span created → OpenTelemetry
   
3. SUMMARIZER AGENT
   ├─ LLM call → Summary
   ├─ Telemetry logged → LLM_CALLS
   └─ Span created → OpenTelemetry
   
4. NOTIFIER AGENT
   ├─ LLM call → Outreach message
   ├─ Telemetry logged → LLM_CALLS
   └─ Span created → OpenTelemetry
   
5. OUTPUT VALIDATION
   ├─ PII detection & redaction
   └─ Redacted outputs
   
6. AUDIT & FEEDBACK
   ├─ Hash-chained audit record created
   ├─ LLM-as-Judge evaluates quality
   └─ Results logged
   
7. DASHBOARD AGGREGATION
   └─ Metrics updated
```

### Error Paths

#### Input Validation Failure
```
INPUT → Guardrail check fails
        ↓
        Block request
        ↓
        Log GuardResult
        ↓
        Return status: 'input_guard_blocked'
```

#### Rate Limit Encountered
```
LLM call → Rate limit (429)
         ↓
         Token bucket rate limiting
         ↓
         Exponential backoff retry
         ↓
         Eventually succeeds or max retries exceeded
         ↓
         Retry count recorded in LLMResult
```

#### Budget Exceeded
```
LLM call → Cost estimated
         ↓
         Compare: cumulative_cost + new_cost vs. budget
         ↓
         If exceeds: raise BudgetExceededError
         ↓
         Batch processing halts
         ↓
         Log 'budget.exceeded' event
         ↓
         Return status: 'budget_exceeded'
```

---

## Configuration & Deployment

### Environment Variables

```bash
# LLM Configuration
ANTHROPIC_API_KEY=<your-api-key>
USE_MOCK=False                        # Set to True for mock/demo mode

# Budget
GLOBAL_BUDGET_USD=0.01               # Cost ceiling per batch

# Rate Limiting
RATE_LIMIT_CAPACITY=10               # Token bucket capacity
RATE_LIMIT_REFILL_PER_SEC=2          # Tokens refilled per second

# Tracing
OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317  # Jaeger endpoint
```

### Running in Mock Mode (No API Key Required)

```python
USE_MOCK = True
# The system simulates LLM responses with deterministic outputs
# Useful for testing, demos, and full reproducibility
```

### Running Live

```python
USE_MOCK = False
# Requires ANTHROPIC_API_KEY set
# Makes real API calls to Claude
```

### OpenTelemetry Setup (Optional)

To visualize traces in Jaeger:

```bash
# Start Jaeger via Docker
docker run -d \
  -p 4317:4317 \
  -p 16686:16686 \
  jaegertracing/all-in-one

# Access UI at http://localhost:16686
```

---

## PII Detection Performance

Example evaluation against a synthetic test set:

```
--- PII Detection Metrics (Per Type) ---

EMAIL:
  TP: 3, FP: 0, FN: 0
  Precision: 1.00, Recall: 1.00, F1-Score: 1.00

PHONE:
  TP: 3, FP: 1, FN: 0
  Precision: 0.75, Recall: 1.00, F1-Score: 0.86

NAME:
  TP: 4, FP: 0, FN: 0
  Precision: 1.00, Recall: 1.00, F1-Score: 1.00

ADDRESS:
  TP: 0, FP: 0, FN: 3
  Precision: 0.00, Recall: 0.00, F1-Score: 0.00 ⚠ Needs improvement

NATIONAL_ID:
  TP: 0, FP: 0, FN: 2
  Precision: 0.00, Recall: 0.00, F1-Score: 0.00 ⚠ Needs improvement

--- Overall Metrics ---
Overall TP: 10, FP: 1, FN: 5
Overall Precision: 0.91
Overall Recall: 0.67
Overall F1-Score: 0.77
```

**Interpretation:**
- Email, Phone, and Name detection are robust
- Address and National ID patterns require refinement
- High precision (0.91) means few false positives
- Moderate recall (0.67) means some real PII is missed

---

## Audit Log Persistence Example

### Saving

```
Saving audit log to audit_log.jsonl...
Audit log with 24 records saved.
```

### Loading & Verification

```
Loading audit log from audit_log.jsonl...
Loaded 24 records from audit_log.jsonl.
Hash chain successfully verified for loaded audit log.
Reloaded audit log has 24 records.
```

---

## Glossary

| Term | Definition |
|------|-----------|
| **Span** | A unit of work within a trace, with duration and attributes |
| **Trace** | An end-to-end request spanning multiple spans |
| **PII** | Personally Identifiable Information (emails, phones, names, etc.) |
| **Guardrail** | A rule that validates or blocks unsafe inputs/outputs |
| **Telemetry** | Metrics collected about system behavior (tokens, latency, cost) |
| **Hash Chain** | A series of cryptographically linked records for integrity |
| **Token Bucket** | Rate limiting mechanism allowing bursts then sustained rate |
| **LLM-as-Judge** | Using an LLM to evaluate output quality |
| **Audit Log** | Immutable record of all LLM interactions |
| **Redaction** | Replacing sensitive data with generic tokens |

---
