# ProposalForge — Multi-Agent Architecture (FIAA-style)

ProposalForge now runs as a **multi-agent pipeline** with full observability,
a RAGAS quality gate, and Docker + Prometheus + Grafana — modelled on the FIAA
fraud-investigation design, applied to proposal/document analysis.

## The pipeline (hub-and-spoke)
A **Supervisor** (`core/pipeline.py::run_pipeline`) orchestrates five agents
(`core/agents.py`):

| Agent | Job |
|-------|-----|
| **Intake** | Parses & classifies the uploaded document(s) |
| **Retrieval** | RAG over all docs (FAISS / Pinecone / TF-IDF) with source attribution |
| **Research** | External research notes (offline knowledge stub by default) |
| **Report** | Produces the report: narrative, objective, challenges, solutions, evidence table, recommended actions, and a 1–10 quality score |
| **Evaluator** | RAGAS quality gate: faithfulness · relevance · context-recall → APPROVE / FLAG |

Every agent call flows through one `@track_agent` decorator
(`core/observability.py`) that emits to all three observability pillars at once.

## DEMO mode (zero keys)
Leave all API keys blank and the whole pipeline runs in **DEMO MODE**: the offline
LLM client produces deterministic grounded output and the TF-IDF retriever indexes
the documents. Add a Groq or Claude key for live LLM reasoning. Backend selection
is automatic (Groq → Claude → offline).

## Observability
- **structlog** JSON logs, `run_id`-bound, secrets redacted → `logs/run_<id>.jsonl` + `logs/pf.jsonl`
- **Prometheus** metrics at `GET /metrics` (FastAPI): `pf_agent_calls_total`,
  `pf_agent_latency_seconds`, `pf_llm_tokens_total`, `pf_guardrail_hits_total`,
  `pf_pipeline_latency_seconds`, `pf_last_quality_score`, `pf_active_runs`,
  `pf_supervisor_iterations_total`, `pf_ragas_faithfulness`
- **Grafana** board + 5 Prometheus **alert rules** (`monitoring/alert_rules.yml`)
- All three degrade to no-ops if a library is missing, so the app always runs.

## Dashboard — the "🤖 Agent Pipeline" tab
Run a task over the uploaded documents and see, live: an animated SVG quality
gauge, the agent timeline (status + latency per agent), the report with an
evidence table and recommended actions, the RAGAS scores, the gate verdict, the
guardrail audit, and a one-click JSON download of the whole investigation.

## Run it

DEMO mode (no keys):
```
pip install -r requirements.txt
streamlit run app_prod.py        # open the Agent Pipeline tab
```

Full stack with metrics + Grafana (Docker):
```
cp .env.example .env             # optionally add GROQ_API_KEY
docker compose up -d
# Dashboard  http://localhost:8000      (Streamlit)
# API+metrics http://localhost:8001/metrics
# Prometheus http://localhost:9090
# Grafana    http://localhost:3000      (admin / proposalforge2025)
```

## Tests
`tests/test_pipeline.py` covers the pipeline, agents, RAGAS gate, the
`@track_agent` decorator and the metrics payload. Run them from the
**🧪 Tests & Coverage** tab or `pytest tests -q`.
