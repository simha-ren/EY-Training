# Multi-document analysis + Tests & Coverage

## Multi-document analysis
- The **Upload & Analyze** tab now accepts **multiple files at once** (drag in
  several, or add more later). Each document is analyzed individually.
- A **Documents** table shows every uploaded file with type, size, character
  count and analysis confidence. A selector lets you view any document's full
  analysis (objective / challenges / solutions / insights), and you can remove a
  document.
- The **Chat** builds a single combined vector index across **all** documents, so
  questions are answered across the whole set. Each answer shows a **📎 Sources**
  line listing which document(s) the answer was drawn from.
- Works with any backend (FAISS / Pinecone / TF-IDF); source attribution is
  tracked per chunk.

## Tests & Coverage tab
- New **🧪 Tests & Coverage** tab runs the automated `pytest` suite with
  `coverage` and shows, live in the UI:
  - KPIs: total / passed / failed / skipped tests and overall coverage %.
  - A pass-rate progress bar and run duration.
  - A per-test table (name, suite, time, status).
  - A per-module coverage table and bar chart.
- Click **▶️ Run test suite**. Requires `pip install pytest coverage`
  (added to `requirements.txt`).

### The test suite (`tests/`)
Hermetic unit tests for the core modules:
- `test_metrics.py` — groundedness / usefulness / accuracy / extractive answer
- `test_retriever.py` — chunking, single + multi-doc retrieval, source attribution
- `test_audit_logger.py` — logging, evaluation metrics, WAL mode
- `test_claude_llm.py` — offline answering, clarification, suggestions
  (uses `monkeypatch` so results are deterministic even if an API key is set)
- `test_file_processor.py` — supported file types

Run from the command line too:
```
pytest tests -q
coverage run --source=core -m pytest tests && coverage report
```

Note: coverage (~23%) focuses on `core/`. The numbers are real, not mocked — the
LLM/Pinecone network branches aren't exercised offline, which is expected.
