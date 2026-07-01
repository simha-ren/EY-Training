# Production Features Guide

This document covers the production-readiness features, all built on free /
open-source components (no Azure OpenAI, no paid SaaS required).

## 1. Performance — sub-5ms retrieval (rps < 5ms)
- The retriever now has an **auto-invalidating query cache**: repeated queries
  return from memory in microseconds; the cache clears automatically when the
  document set changes.
- Cold (uncached) retrieval on a production ANN backend is already < 5ms:
  measured **FAISS ≈ 0.17 ms**, **Qdrant ≈ 0.96 ms** on ~140 chunks.
- `retriever.last_latency_ms` exposes the latency of the last uncached query.
- **Recommendation:** use `VECTOR_BACKEND=faiss` for single-node and
  `qdrant` for a shared production service.

## 2. FAISS → production vector DB (prototype → production)
- **Prototype:** `VECTOR_BACKEND=faiss` (in-process, zero infra).
- **Production (free, open-source):** `VECTOR_BACKEND=qdrant` (Docker service
  included) or `pgvector` (one Postgres for data + vectors).
- **Managed option:** `VECTOR_BACKEND=pinecone` (needs `PINECONE_API_KEY`).
- All share one interface (`build_documents`, `search → [{text,score,source}]`),
  so switching is a config change — no business-logic edits.

```
# prototype
VECTOR_BACKEND=faiss
# production (free)
VECTOR_BACKEND=qdrant
QDRANT_URL=http://qdrant:6333
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
```

## 3. End-to-end evaluation with a real document
Run the harness against any document:
```
python evaluate.py path/to/document.pdf
```
It runs RAG + the multi-agent pipeline over a real document and writes
`reports/EVALUATION_REPORT.md` + `reports/evaluation.json`, reporting retrieval
latency, groundedness/usefulness/accuracy, RAGAS faithfulness/relevance/recall,
the pipeline score + gate verdict, and that PII/PHI questions are blocked.

## 4. Observability — LangSmith (and Langfuse) for the LLM
`core/tracing.py` traces the pipeline and each agent. Provider is chosen by env:
- **LangSmith:** `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` (+ optional
  `LANGCHAIN_PROJECT`). View trace trees at smith.langchain.com.
- **Langfuse (open-source, self-hostable):** `LANGFUSE_PUBLIC_KEY` +
  `LANGFUSE_SECRET_KEY` (+ `LANGFUSE_HOST`).
- **None:** with no keys, tracing is a no-op so the pipeline still runs.

This complements the existing Prometheus metrics + Grafana dashboard and the
structlog JSON logs (`logs/run_<id>.jsonl`).

## 5. Chatbot with PII/PHI protection
- The chat supports **multi-turn memory** (recent exchanges are fed back so
  follow-up questions stay coherent).
- Every turn passes through the **PII/PHI guardrails first** (input + output +
  soft-phrasing) — memory cannot bypass them. Sensitive requests are refused with
  the named guardrail; benign questions are answered with source attribution.

## 6. Login / sessionization
- `core/auth.py` provides users + sessions in SQLite (WAL), passwords hashed with
  **PBKDF2-HMAC-SHA256** (stdlib — no external dependency).
- The app shows a **login gate**; users can sign in or create an account, and the
  sidebar shows the signed-in user with a **logout** button.
- Sessions expire after `SESSION_TTL_SECONDS` (default 8h).
- A default **admin / admin123** is seeded on first run — change it via
  `DEFAULT_ADMIN_PASSWORD` (and delete/replace the admin user) in production.
- Set `REQUIRE_AUTH=false` to disable the gate for local/demo use.

### Security notes
- Passwords are never stored in plaintext; sessions are random 256-bit tokens.
- For internet-facing production, terminate TLS at a reverse proxy (Nginx/Traefik)
  and consider OAuth/SSO in front of the app.
