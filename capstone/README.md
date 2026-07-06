# ProposalForge Pro

A domain-aware **Retrieval-Augmented Generation (RAG)** assistant for reading and
answering questions about proposals and documents across three domains —
**agriculture, finance, healthcare**. It routes each query to the right domain,
retrieves grounded context, and composes an answer with guardrails, follow-up
suggestions, and an offline fallback so it always responds.

Ships as a single container (Streamlit UI + FastAPI service behind nginx) with
CI/CD to **Azure Web App for Containers**.

## Structure

```
capstone/
├─ src/
│  ├─ agents/        LLM clients + generation/suggestion agents
│  ├─ orchestrator/  control loop, routing, async jobs
│  ├─ retrieval/     vector + RAG
│  ├─ common/        shared services (config, guardrails, metrics, auth, …)
│  ├─ api/           FastAPI endpoints (/health, /metrics, /api/v1/*)
│  └─ ui/            Streamlit frontends
├─ infra/            Dockerfiles, docker-compose, Azure Bicep/IaC, nginx, monitoring
├─ tests/            unit + integration + load (tests/load)
├─ docs/             architecture.md, decisions.md, and original design notes
├─ .github/workflows/  ci.yml (tests) + azure.yml (build → push → deploy → load-test)
├─ requirements.txt  .env.example  .gitignore  pytest.ini
└─ worker.py start.py evaluate.py
```

See [`docs/architecture.md`](docs/architecture.md) for the full design and request flow.

## Quickstart (local)

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then add GROQ_API_KEY (free) or CLAUDE_API_KEY

# From the repo root so `src` is importable:
export PYTHONPATH=.           # Windows (PowerShell): $env:PYTHONPATH="."

# Streamlit UI
streamlit run src/ui/app_prod.py
# FastAPI (in another shell)
uvicorn src.api.api_server:app --reload --port 8001
```

No key? It still runs — answers come from the offline extractive fallback and are
labelled as such.

## LLM backends
Selected automatically by `src/agents/llm_backend.py`: **Azure OpenAI** (if
`AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY`) → **Groq** (if `GROQ_API_KEY`) →
**Claude** (if `CLAUDE_API_KEY`/`ANTHROPIC_API_KEY`) → local OpenAI-compatible
(`LLM_BASE_URL`) → **offline extractive**. Azure OpenAI is the production connector
(auto-wired by Bicep); Groq is a good free local default.

## Production features (Azure)

- **LLM connector:** Azure OpenAI + a model deployment provisioned by Bicep; endpoint/
  key/deployment injected as app settings.
- **Vector DB:** Pinecone (`VECTOR_BACKEND=auto` uses it when `PINECONE_API_KEY` is set,
  else faiss/tf-idf).
- **Multi-doc analysis:** `POST /api/v1/analyze/multi` runs the pipeline across several
  documents via the connector; `POST /api/v1/retrieve` is a fast retrieval-only path.
- **Observability + traceability:** Prometheus `/metrics` + per-run traces to Azure
  Monitor / Application Insights (auto-wired).
- **Autoscale:** App Service Plan scales 1→5 on CPU (Bicep autoscale rule).
- **Load + latency testing:** `tests/load/locustfile.py` enforces `/health` p95 < 50 ms,
  `/api/v1/retrieve` p95 < 50 ms, end-to-end p95 < 5 s, and fails CI if breached.
  `tests/load/loadtest.yaml` targets Azure Load Testing for cloud-scale runs.
- **End-to-end evaluation:** `python eval/eval_realdoc.py` (real doc, groundedness gate)
  and `python -m eval.evaluate` (golden set). Both run in CI before deploy.

> Latency note: `<5 ms` is impossible for an LLM call (generation is hundreds of ms to
> seconds). The 50 ms budgets apply to health and retrieval-only; end-to-end is
> p95 < 5 **seconds**.

## Tests

```bash
pytest tests            # pytest.ini sets pythonpath=.
# with coverage:
coverage run --source=src -m pytest tests && coverage report
```
Load test (`tests/load/locustfile.py`) runs in CI against the deployed host.

## Run with Docker

```bash
# Production-shaped single container (nginx :8080 → Streamlit + FastAPI)
docker build -f infra/Dockerfile.azure -t proposalforge:local .
docker run -p 8080:8080 -e GROQ_API_KEY=<key> proposalforge:local
curl localhost:8080/health

# Or the dev stack (adds qdrant + ollama)
docker compose -f infra/docker-compose.yml up --build
```

## Observability

Two layers that do different jobs:

- **Metrics (Prometheus)** — aggregate counts/latency at `/metrics`. Prometheus +
  Grafana run locally via `infra/docker-compose.yml` (`infra/monitoring/` has the
  config + dashboard). Always on, no setup.
- **Tracing (Azure Monitor — production default)** — per-run trace trees
  (pipeline → agents → LLM) with tokens, RAGAS scores, and guardrail hits.
  `get_tracer()` selects **Azure Monitor → LangSmith → Langfuse → no-op**.

On Azure, tracing is **zero-config**: the Bicep template provisions Application
Insights and injects `APPLICATIONINSIGHTS_CONNECTION_STRING`, so telemetry flows to
Azure Monitor automatically — view it under Application Insights in the portal. For
LLM-level traces during local development, opt into LangSmith by setting
`LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` in `.env`. With nothing set,
tracing is a safe no-op.

## Deploy to Azure (CI/CD)
Push to `main` and GitHub Actions runs **test → build/push to ACR → deploy → load-test**.
Full walkthrough — secrets, provisioning, and the required WebSockets setting — is in
[`DEPLOY_RUNBOOK.md`](DEPLOY_RUNBOOK.md).

Three repo secrets are required: `AZURE_CREDENTIALS`, `ACR_NAME`, `AZURE_WEBAPP_NAME`
(plus a `production` GitHub Environment).

> Note: the pipeline runs in **your** GitHub repo against **your** Azure using those
> secrets — set them once and every push to `main` deploys.

## Notes
Some modules were reconstructed from a partially corrupt backup
(`src/agents/groq_llm.py`, `src/orchestrator/router.py`, `worker.py`); details in
[`docs/decisions.md`](docs/decisions.md).
