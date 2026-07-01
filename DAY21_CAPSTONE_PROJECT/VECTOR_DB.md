# Vector DB (Pinecone / FAISS) — retrieval-augmented answers

## What changed and why
Previously the chat sent the model the **first 3000 characters** of a document, so
questions about anything later in a long document failed. Now the document is
**chunked, embedded, and indexed**, and each question retrieves only the most
relevant chunks as context. This improves answer accuracy and groundedness and is
the "accuracy of the answer" item from the team notes.

New module: `core/retriever.py`. The chat builds an index when you analyze a
document and retrieves the top-4 relevant chunks per question.

## Three backends (auto-selected)
Set `VECTOR_BACKEND` to `auto` (default), `pinecone`, `faiss`, or `tfidf`.

- **tfidf** — sklearn TF-IDF + cosine. Zero setup, always available. Default fallback.
- **faiss** — local vector DB. `pip install faiss-cpu`. Chosen automatically when present.
- **pinecone** — cloud vector DB. `pip install pinecone`, set `PINECONE_API_KEY`
  (and optionally `PINECONE_INDEX`, default `proposalforge`). Chosen automatically
  when a key is present.

Selection order for `auto`: Pinecone (if key) → FAISS (if installed) → TF-IDF.
The active backend is shown in the Chat tab status line and after indexing.

## Embeddings (for faiss / pinecone)
- If `sentence-transformers` is installed, semantic embeddings (`all-MiniLM-L6-v2`)
  are used automatically.
- Otherwise a dependency-light hashing embedding is used, so FAISS/Pinecone work
  out of the box without downloading a large model. Install
  `sentence-transformers` for better semantic recall.

## How to enable each
FAISS (recommended local default):
```
pip install faiss-cpu
# nothing else needed; VECTOR_BACKEND=auto will pick it
```
Pinecone (cloud):
```
pip install pinecone sentence-transformers
set PINECONE_API_KEY=your_key
set VECTOR_BACKEND=pinecone
```
TF-IDF only (no extra installs):
```
set VECTOR_BACKEND=tfidf
```

## How the team-notes list maps to the app
- **Suggestions / Autosuggest** — implemented (suggestion chips; work online & offline).
- **Routing keywords** — the multi-domain engine (`core/router.py`, used by `app.py`)
  already routes by keywords; `app_prod.py` now does semantic retrieval instead.
- **Backend pending** — fixed: chat works via Groq / Claude / offline fallback.
- **Observability + Guardrails** — Guardrails run on every answer; the Audit Logs
  and Analytics tabs provide observability (per-query accuracy, groundedness,
  usefulness, guardrail triggers).
- **Accuracy of the answer** — composite accuracy (confidence · groundedness ·
  usefulness), now improved by retrieval.
- **Plan B for Azure Architecture / deployment** — see `DEPLOYMENT.md` and
  `PRODUCTION_PLAN.md`.
- **20 breakup tasks in GitHub** — project management; not a code change.
