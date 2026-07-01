# Deployment Guide — ProposalForge Pro

Everything below is **free and open-source** — no Azure OpenAI, no paid SaaS.

## What you get, deployed
| Concern | Component (free/OSS) | Port |
|---------|----------------------|------|
| Dashboard (UI) | Streamlit | 8000 (internal) |
| API + webhook + `/metrics` | FastAPI/uvicorn | 8001 (internal) |
| Reverse proxy + TLS | Nginx | 80 / 443 |
| Vector DB | Qdrant | 6333 |
| LLM | Ollama (Llama 3.x) / vLLM | 11434 |
| Metrics | Prometheus | 9090 |
| Dashboards | Grafana | 3000 |
| Tracing (optional) | LangSmith or Langfuse | — |
| Data | SQLite (WAL) or PostgreSQL + pgvector | — |

## Production features (all implemented)
- **Chat sessionization** — per-user chat sessions persist across refresh/logout
  (`core/chat_store.py`); switch/create/delete from the sidebar.
- **Login/sessionization** — PBKDF2-hashed accounts + expiring sessions (`core/auth.py`).
- **rps < 5ms** — retrieval cache + FAISS/Qdrant (cold ~0.17-0.96ms, warm ~0ms).
- **Production RAG** — Qdrant / pgvector backends, BGE embeddings.
- **LangSmith observability** — set env vars and each agent run is traced.
- **End-to-end evaluation** — `python evaluate.py <doc>` -> `reports/EVALUATION_REPORT.md`.

## 1. Configure
```
cp .env.production.example .env
# edit: DEFAULT_ADMIN_PASSWORD, VECTOR_BACKEND, LLM_*, optional tracing keys
```

## 2. Launch the full stack
```
make prod          # compose up with the prod overlay (adds nginx)
make pull-model    # one-time: pull llama3.1:8b into Ollama
```
- App        http://<host>/          (Nginx -> Streamlit)
- API        http://<host>/api/...   (webhook, pipeline)
- Prometheus http://<host>:9090
- Grafana    http://<host>:3000      (admin / proposalforge2025 - change it)

## 3. HTTPS
1. Put `fullchain.pem` + `privkey.pem` in `deploy/certs/`.
2. Uncomment the `listen 443 ssl` block + HTTP->HTTPS redirect in `deploy/nginx.conf`.
3. Recreate nginx.

## 4. First-run checklist
- [ ] Sign in as admin; create real users.
- [ ] Upload a doc; chat status shows Qdrant.
- [ ] Run Agent Pipeline; see score + RAGAS gate.
- [ ] `curl http://<host>/api/health` -> ok.
- [ ] Fire a webhook job; see it in the pipeline inbox.
- [ ] Grafana -> ProposalForge -> Last 15 minutes -> panels fill.
- [ ] `python evaluate.py` -> review the report.

## 5. Scaling (all free)
- Vector DB: Qdrant (millions of vectors) or pgvector on your Postgres.
- LLM throughput: swap Ollama for vLLM/TGI via `LLM_BASE_URL`.
- Workers: Celery/RQ + Redis for many concurrent pipelines.
- App replicas behind Nginx; share state in Postgres (`DATABASE_URL`).

## 6. Backups
Persist volumes: app `data/` (SQLite), `qdrant-data`, `ollama-data`, `grafana-data`.

## 7. Security
- Change admin + Grafana passwords. App ports bound to localhost; only Nginx public.
- `/metrics` IP-restricted in nginx.conf. TLS at Nginx. Secrets via `.env` only.

## Common issues
- Grafana empty: run the pipeline once; widen the time range.
- Ollama slow first call: model downloads on first pull; then fast.
- Login loop: clear cookies or set `REQUIRE_AUTH=false` to check.
