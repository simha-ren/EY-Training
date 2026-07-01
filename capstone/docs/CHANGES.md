# What was fixed / added

This document summarizes the changes made to **ProposalForge Pro** (`app_prod.py`
and the FastAPI backend `api_server.py`).

## 1. Chat now always generates an answer
**Problem:** the chat returned a dead `"Unable to generate answer"` whenever the
Claude API call failed (no key, expired key, no credits, model access, rate
limit, etc.). There was no fallback.

**Fix (`core/claude_llm.py`):**
- The client now tracks an `online` flag and `last_error`, and accepts either
  `CLAUDE_API_KEY` or the SDK-standard `ANTHROPIC_API_KEY`.
- When Claude is unavailable or errors, the chat transparently falls back to a
  **grounded extractive answer** built from the most relevant sentences of your
  document (`core/metrics.py::extractive_answer`). The app *always* answers.
- Online responses parse a `Confidence: NN%` marker robustly (anywhere in the
  reply), and derive confidence from grounding if the model omits it.
- Each answer reports its `mode` (`claude` or `offline`) so the UI can show it.

## 2. Markdown (`.md`) support
- The uploader and `FileProcessor` already accept `.md`; this was verified
  end-to-end. Markdown is stripped of formatting and indexed like any other doc.

## 3. Accuracy score on groundedness + usefulness + confidence
**New `core/metrics.py`** centralizes the three component scores used by both the
UI and the API:
- **groundedness** — fraction of the answer's content words supported by the source
- **usefulness** — substantive vs. a punt / too-short answer
- **confidence** — the model's (or fallback's) confidence
- **accuracy_score = mean(confidence, groundedness, usefulness)**

Every chat turn is scored and logged with all four values.

## 4. Accuracy-score route + analytics + autosuggestion (API)
`api_server.py` routes:
- `GET  /api/v1/analytics/accuracy`   — composite accuracy score
- `GET  /api/v1/analytics/evaluation` — full breakdown + per-query history (new)
- `GET  /api/v1/analytics/summary`    — analytics summary
- `POST /api/v1/documents/{id}/query` — now returns `evaluation` metrics + `mode`
- `POST /api/v1/documents/{id}/suggestions` — autosuggestion route (new)

## 5. Audit Logs tab (UI) — fixed crash + history
**Problem:** the Audit Logs tab called `AuditLogger.get_evaluation_metrics(...)`,
which did not exist → `AttributeError` crashed the tab.

**Fix (`core/audit_logger.py`):** added `get_evaluation_metrics()` which
aggregates per-query confidence/groundedness/usefulness, computes the composite
accuracy, and returns a per-query history. `get_analytics_summary()` now reports
accuracy as that composite (falling back to analysis confidence when no queries
exist yet). The Audit Logs tab shows the full event history table plus the
evaluation metrics.

## 6. Analytics tab (UI)
Replaced the hardcoded placeholder charts with **real** data: top-line KPIs, the
confidence/groundedness/usefulness breakdown, and a per-query accuracy trend.

## 7. Autosuggestion (UI)
- Suggestion chips now **submit the question directly** (previously they only
  inserted a confusing "Suggested: ..." line).
- Suggestions work offline too (heuristic follow-ups derived from the document).

---

## Running it

```bash
pip install -r requirements.txt

# Optional: enable Claude (otherwise the app runs in grounded offline mode)
export CLAUDE_API_KEY="sk-ant-..."   # or ANTHROPIC_API_KEY

# UI
streamlit run app_prod.py

# API (separate process)
python api_server.py        # serves on :8001
```

The app is fully functional **without** an API key — chat, analysis, suggestions,
accuracy scoring, analytics and audit logs all work in grounded offline mode.

## 8. Groq backend (free-tier LLM alternative to Claude)

Added `core/groq_llm.py` (OpenAI-compatible Groq client, same interface as the
Claude client) and `core/llm_backend.py`, a selector that picks the backend at
startup:

  **Groq (if `GROQ_API_KEY` set) → Claude (if `CLAUDE_API_KEY`/`ANTHROPIC_API_KEY` set) → offline.**

To use Groq (free tier at https://console.groq.com):

Windows cmd (current terminal):
```
set GROQ_API_KEY=gsk_your_key_here
streamlit run app_prod.py
```
Or add to `.env`:
```
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```
Restart Streamlit after setting the key. The chat status line and each answer's
badge show which backend produced it (⚡ Groq / 🟢 Claude / ⚪ Offline).

Note: `ngrok` is a tunneling tool, not an LLM — its key cannot generate answers.
Groq *can*, because it serves open models over an OpenAI-compatible API.
