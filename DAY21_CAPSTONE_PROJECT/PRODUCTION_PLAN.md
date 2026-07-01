# Production Plan for 100+ Users

This complements the existing `DEPLOYMENT.md`. It focuses on the one question that
changes the design: **how to run this for 100 or more users reliably.**

## TL;DR sizing

"100 users" is not "100 simultaneous LLM calls." Plan around *concurrent active
requests* — usually 10–20% of your user count. For 100 users:

| Component | Start with | Notes |
|---|---|---|
| Streamlit UI (`app_prod.py`) | 2–4 replicas, 1 vCPU / 1–2 GB each | Scale **replicas**, not threads. Needs sticky sessions. |
| FastAPI API (`api_server.py`) | 2 replicas × `uvicorn --workers 2` | Stateless; scales easily. Put automation/bulk traffic here. |
| Database | PostgreSQL, 2 vCPU / 4 GB | Replaces SQLite once you have >1 replica. |
| Real bottleneck | **LLM provider rate limit** | Use a paid Groq/Anthropic tier + backoff, not the free tier. |

## Why the current single container isn't enough at 100 users

- **Streamlit holds one server-side session per user over a websocket.** A single
  process is fine for a handful of users but not hundreds. The fix is horizontal:
  several UI replicas behind a load balancer with **sticky sessions** (a user must
  stay pinned to the same replica — use `ip_hash` in Nginx or a cookie-affinity
  Ingress).
- **SQLite is a single local file.** It's now tuned with WAL mode + a busy timeout
  (good for one replica), but multiple replicas can't share one file safely.
  Move to Postgres and point the app at it with `DATABASE_URL` / `AUDIT_DB_PATH`.

## The three things to change from the demo setup

1. **Split UI and API into separate services** and run 2+ replicas of each behind
   Nginx/your cloud load balancer with TLS and sticky sessions for the UI.
2. **Switch the audit DB to PostgreSQL** on a managed service or a dedicated
   container with a persistent volume + backups. (The schema is unchanged; only the
   driver in `core/audit_logger.py` swaps from `sqlite3` to `psycopg2`/SQLAlchemy.)
3. **Use a paid LLM tier with backoff + a small queue.** The app already fails soft
   to grounded offline answers on rate limits, so users never hit a hard error —
   but you want backoff so you respect provider limits and keep answer quality high.

## What's already production-friendly here

- **Graceful degradation:** if the LLM key is missing/rate-limited/out of credit,
  the chat returns grounded offline answers instead of erroring — a provider
  outage can't take the whole service down.
- **Stateless answering:** no per-request server state beyond the shared DB, so
  replicas are interchangeable.
- **Built-in observability:** the Analytics and Audit Logs tabs already track per
  user queries, accuracy, groundedness, usefulness and guardrail triggers.
- **Health endpoint:** `GET /health` for readiness/liveness probes.
- **Config by env:** keys and DB path are read from the environment, so nothing
  sensitive lives in the image.

## Concrete next steps (in order)

1. Run the provided `docker compose up --build` with a `GROQ_API_KEY` set — verify
   end to end on one box.
2. Put Nginx + TLS + a domain in front (see `DEPLOYMENT.md` §reverse proxy).
3. Stand up Postgres; migrate the audit logger; set `DATABASE_URL`.
4. Split into UI + API services, scale each to 2 replicas, enable sticky sessions.
5. Add autoscaling on CPU/request metrics and an APM (Prometheus/Grafana or your
   cloud's). Enable DB backups.

## Hard limits to watch

- **LLM rate limits** are the ceiling on throughput — size your provider tier to
  your peak concurrent requests, not your user count.
- **Upload size:** set Streamlit `server.maxUploadSize` to cap large files.
- **Auth:** the built-in `user_id` is a demo placeholder. Put real authentication
  (SSO / an OAuth proxy) in front before going live.
