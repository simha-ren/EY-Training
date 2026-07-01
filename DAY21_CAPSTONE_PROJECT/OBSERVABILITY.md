# Observability — LangSmith

ProposalForge uses **LangSmith** as its observability layer. Prometheus and
Grafana have been removed from the stack.

## What is traced
Every pipeline run and each agent is a span in a LangSmith trace tree, carrying
real signal:
- **Run level:** backend (groq/claude/local/offline), demo_mode, quality score,
  total tokens, RAGAS (faithfulness/relevance/recall/overall), gate verdict,
  guardrail hits, end-to-end latency.
- **Per agent:** intake, retrieval (sources/hits), research, report
  (score, mode, tokens, narrative), evaluator (RAGAS).
- **Chat:** each interactive Q&A is traced (mode, confidence, tokens, sources).

## Enable it
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-your-key
LANGCHAIN_PROJECT=proposalforge      # optional
```
Open your traces at https://smith.langchain.com. With no key set, tracing is a
no-op and the app still runs.

## Open-source alternative — Langfuse (self-hostable, free)
```
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=http://localhost:3001   # your self-hosted instance
```
Selection order: LangSmith → Langfuse → no-op.

## Notes
- Structured JSON logs per run remain in `logs/run_<id>.jsonl` (structlog).
- The `/metrics` endpoint still exists but is no longer scraped; the compose
  stack no longer starts Prometheus or Grafana.
- `requirements.txt` now includes `langsmith`.
