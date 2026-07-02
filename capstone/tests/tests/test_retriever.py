import os
os.environ["VECTOR_BACKEND"] = "tfidf"  # deterministic, no heavy deps
from core.core.retriever import chunk_text, TfidfRetriever, get_retriever

DOCS = [
    {"id": "1", "name": "millet.md",
     "text": "Millet scheme. Subsidy INR 5000 per hectare. MSP INR 3846 per quintal."},
    {"id": "2", "name": "solar.md",
     "text": "Rooftop solar policy. Capital subsidy of 40 percent up to 3 kW."},
]

def test_chunking_nonempty():
    assert len(chunk_text("a paragraph. " * 200)) >= 1

def test_build_and_search_single():
    r = TfidfRetriever(); r.build("Subsidy INR 5000 per hectare for farmers.", "d1", "d1.md")
    hits = r.search("subsidy amount", top_k=1)
    assert hits and "5000" in hits[0]["text"]

def test_multi_doc_source_attribution():
    r = TfidfRetriever(); r.build_documents(DOCS)
    assert set(r.doc_names) == {"millet.md", "solar.md"}
    hits = r.search("solar capital subsidy percent", top_k=1)
    assert hits[0]["source"] == "solar.md"

def test_factory_returns_retriever():
    assert get_retriever().backend in ("tfidf", "faiss", "pinecone")


def test_qdrant_backend_in_memory(monkeypatch):
    monkeypatch.setenv("VECTOR_BACKEND", "qdrant")
    monkeypatch.delenv("QDRANT_URL", raising=False)  # in-memory
    import importlib, core.retriever as R
    importlib.reload(R)
    r = R.get_retriever()
    assert r.backend in ("qdrant", "faiss", "tfidf")  # qdrant if client installed
    r.build_documents(DOCS)
    hits = r.search("solar capital subsidy percent", top_k=1)
    assert hits and hits[0]["source"] == "solar.md"
    importlib.reload(R)  # restore default factory state


def test_pgvector_falls_back_without_db(monkeypatch):
    monkeypatch.setenv("VECTOR_BACKEND", "pgvector")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib, core.retriever as R
    importlib.reload(R)
    r = R.get_retriever()
    assert r.backend in ("faiss", "tfidf")  # graceful fallback, never crashes
    importlib.reload(R)
