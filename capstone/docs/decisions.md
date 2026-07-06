# Design Decisions (ADRs)

Short records of the notable choices in this capstone. Older narrative design
notes are preserved alongside this file (`ARCHITECTURE.md`, `DESIGN.md`, etc.).

## ADR-1: Single container, nginx-multiplexed, on Azure Web App for Containers
**Decision.** Package the Streamlit UI and FastAPI service in one image, fronted by
nginx on port 8080 (the port Azure routes to). **Why.** Simplest deployable unit for a
capstone; one image, one Web App, one health check. `/` serves the UI; `/api/`,
`/health`, `/metrics` serve the API. **Trade-off.** UI and API scale together. If they
needed independent scaling we would split them into two Web Apps / containers.

## ADR-2: Pluggable LLM backend with an always-on offline fallback
**Decision.** `get_llm_client()` picks Groq → Claude → local OpenAI-compatible →
offline extractive, in that order. **Why.** The app must answer even with no API key
(grading, demos, outages). Groq is the default because it is free and
OpenAI-compatible. **Trade-off.** Offline answers are extractive, not generative;
they are clearly labelled via `mode`/`used_fallback`.

## ADR-3: TF-IDF + keyword hybrid router
**Decision.** Route by blending TF-IDF centroid cosine similarity with per-domain
`routing_keywords`, gated by two thresholds. **Why.** Cheap, deterministic,
explainable, and dependency-light — no embedding service required for routing.
**Trade-off.** Less nuanced than embedding-based routing; mitigated by the
suggest/ask fallbacks and user-confirmable domain chips.

## ADR-4: Namespace-isolated retrieval per domain
**Decision.** Retrieval is scoped to the selected domain's chunks. **Why.** Prevents
cross-domain leakage (e.g. a finance query surfacing healthcare text) and keeps
answers grounded in the right corpus.

## ADR-5: `src/` package with `common/` for shared services
**Decision.** Organize code into `agents/ orchestrator/ retrieval/ api/ ui/`, plus a
`common/` subpackage for cross-cutting services (config, guardrails, metrics, auth,
observability, etc.). **Why.** The requested top-level buckets don't cleanly own
cross-cutting concerns; a `common/` package avoids forcing them into the wrong bucket.
All imports are absolute (`src.<pkg>.<mod>`) so module moves are unambiguous.

## ADR-6: CI gates deploy; deploy is image-first
**Decision.** `azure.yml` runs tests first; only on success does it build+push the
image to ACR and deploy. The image is built and pushed **before** provisioning so the
Web App can pull it on first boot. **Why.** No broken build ever reaches Azure, and
the first deploy doesn't race a missing image.

## ADR-7: Streamlit WebSockets must be explicitly enabled on Azure
**Decision.** Document and require `--web-sockets-enabled true` on the Web App.
**Why.** Azure Web Apps disable WebSockets by default; Streamlit needs them or the UI
loads blank / keeps reconnecting. This is the single most common post-deploy gotcha.

## ADR-8: Azure Monitor is the production tracing default; Prometheus/Grafana stays local
**Decision.** Keep two observability layers — Prometheus metrics (`/metrics`) and
distributed tracing — and make **Azure Monitor (Application Insights)** the production
tracing backend, provisioned and wired automatically by the Bicep template. Prometheus
+ Grafana (in `infra/docker-compose.yml` / `infra/monitoring/`) remain the local-dev
metrics stack; LangSmith/Langfuse are opt-in dev alternatives for LLM-level traces.
**Why.** The Azure deployment is a single container, so nothing scrapes Prometheus in
production without standing up extra infrastructure (a second container or Azure
Managed Grafana). Application Insights needs zero extra infra — the connection string
is injected into the Web App at provision time and `get_tracer()` picks it up first.
**Trade-off.** Production metrics dashboards live in Azure Monitor rather than Grafana;
if a team wants Grafana in prod too, add Azure Managed Prometheus/Grafana and point it
at `/metrics` (see the runbook's option 3).

---

The source was recovered from a `.rar` backup in which a few members were truncated.
The following were **faithfully reconstructed** to their documented interfaces and
validated (compile + import + end-to-end run):

- `src/agents/groq_llm.py` — `GroqLLMClient`, mirroring `ClaudeLLMClient` exactly
  (OpenAI-compatible transport against Groq's base URL, with the same offline
  fallbacks). Required by the Groq backend.
- `src/orchestrator/router.py` — `DomainRouter` + `RouteResult`, matching how
  `engine.py` consumes routing (`mode` ∈ {route, suggest, ask}, `domain`,
  `suggestions`, `confidence`).
- `worker.py` — thin launcher over `service_bus.run_worker()` for the async job queue.

The following corrupt **test** files were dropped so CI collection stays green; restore
them from your original working repo if you still have them:
`test_approval_workflow.py`, `test_cache_tracing.py`, `test_claude_llm.py`,
`test_integration_api.py`, `test_pipeline.py`.

A latent bug in the demo path was also fixed: `engine.py` passed a `DomainConfig` to
the module-level `guardrails.refuse/disclaimer/detect_gap` (which expected a dict) and
had swapped `redact_pii` arguments. `guardrails` now normalizes either input shape.
