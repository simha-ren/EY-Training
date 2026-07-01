"""Vector retrieval for grounded RAG over one or many uploaded documents.

Documents are chunked, indexed, and searched so each question retrieves only the
relevant chunks - now across *multiple* documents, with the source filename
tracked per chunk so answers can be attributed.

Backends (auto-selected; override with env VECTOR_BACKEND):
  * pinecone - cloud vector DB (PINECONE_API_KEY + PINECONE_INDEX + a lib)
  * faiss    - local vector DB (faiss-cpu)
  * tfidf    - sklearn TF-IDF + cosine; zero setup, always available (default)

search() returns a list of dicts: {"text", "score", "source"}.
"""
from __future__ import annotations

import os
import re
from typing import List, Dict, Any

import numpy as np


# --------------------------------------------------------------------- chunking
def chunk_text(text: str, chunk_size: int = 700, overlap: int = 120) -> List[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries."""
    text = re.sub(r"\r\n", "\n", text or "").strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 1 <= chunk_size:
            buf = f"{buf}\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= chunk_size:
                buf = p
            else:
                start = 0
                while start < len(p):
                    chunks.append(p[start:start + chunk_size])
                    start += chunk_size - overlap
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks or [text[:chunk_size]]


# ------------------------------------------------------------------ embeddings
class _HashingEmbedding:
    """Lightweight dense embedding via sklearn HashingVectorizer."""

    def __init__(self, dim: int = 512):
        from sklearn.feature_extraction.text import HashingVectorizer
        self.dim = dim
        self._vec = HashingVectorizer(n_features=dim, alternate_sign=False, norm=None)

    def encode(self, texts: List[str]) -> np.ndarray:
        mat = self._vec.transform(texts).toarray().astype("float32")
        return _l2_normalize(mat)


class _STEmbedding:
    """Semantic embedding via sentence-transformers (if installed).

    Model is configurable via EMBEDDING_MODEL (default a small, fast, free model;
    set e.g. BAAI/bge-base-en-v1.5 for higher quality in production)."""

    def __init__(self, model_name: str = None):
        from sentence_transformers import SentenceTransformer
        model_name = model_name or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: List[str]) -> np.ndarray:
        emb = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return emb.astype("float32")


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _make_embedding():
    try:
        return _STEmbedding(), "sentence-transformers"
    except Exception:
        return _HashingEmbedding(), "hashing"


# ----------------------------------------------------------------- doc helpers
def _normalize_docs(docs) -> List[Dict[str, str]]:
    """Accept a single text, or a list of {id,name,text} dicts."""
    if isinstance(docs, str):
        return [{"id": "doc", "name": "document", "text": docs}]
    out = []
    for d in docs:
        out.append({"id": str(d.get("id", "doc")),
                    "name": str(d.get("name", d.get("id", "document"))),
                    "text": d.get("text", "")})
    return out


def _chunk_documents(docs: List[Dict[str, str]]):
    chunks: List[str] = []
    sources: List[str] = []
    for d in docs:
        for ch in chunk_text(d["text"]):
            chunks.append(ch)
            sources.append(d["name"])
    return chunks, sources


# -------------------------------------------------------------------- backends
class _BaseRetriever:
    backend = "base"
    embed_info = "none"

    def __init__(self):
        self.chunks: List[str] = []
        self.sources: List[str] = []
        self._cache: Dict[Any, List[Dict[str, Any]]] = {}
        self._cache_token = None
        self.last_latency_ms: float = 0.0

    # Single-document convenience wrapper.
    def build(self, text: str, doc_id: str = "doc", name: str = None):
        return self.build_documents([{"id": doc_id, "name": name or doc_id, "text": text}])

    def build_documents(self, docs):
        raise NotImplementedError

    def _search(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def search(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Cached + timed retrieval. Cache auto-invalidates when the corpus
        changes, so repeated queries return in microseconds (sub-5ms target)."""
        import time
        token = (len(self.chunks), self.chunks[0][:24] if self.chunks else "")
        if token != self._cache_token:
            self._cache = {}
            self._cache_token = token
        key = (query, top_k)
        if key in self._cache:
            self.last_latency_ms = 0.0
            return self._cache[key]
        start = time.perf_counter()
        result = self._search(query, top_k)
        self.last_latency_ms = (time.perf_counter() - start) * 1000.0
        self._cache[key] = result
        return result

    @property
    def doc_names(self) -> List[str]:
        seen = []
        for s in self.sources:
            if s not in seen:
                seen.append(s)
        return seen

    def _format(self, idxs, scores) -> List[Dict[str, Any]]:
        out = []
        for i, s in zip(idxs, scores):
            if i is None or i < 0 or i >= len(self.chunks):
                continue
            out.append({"text": self.chunks[i], "score": float(s),
                        "source": self.sources[i] if i < len(self.sources) else "document"})
        return out


class TfidfRetriever(_BaseRetriever):
    backend = "tfidf"

    def __init__(self):
        super().__init__()
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._Tfidf = TfidfVectorizer
        self.vectorizer = None
        self.matrix = None

    def build_documents(self, docs):
        self.chunks, self.sources = _chunk_documents(_normalize_docs(docs))
        self.vectorizer = self._Tfidf(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(self.chunks)
        return self

    def _search(self, query, top_k=4):
        if not self.chunks:
            return []
        from sklearn.metrics.pairwise import cosine_similarity
        q = self.vectorizer.transform([query])
        sims = cosine_similarity(q, self.matrix)[0]
        order = np.argsort(sims)[::-1][:top_k]
        return self._format(order, [sims[i] for i in order])


class FaissRetriever(_BaseRetriever):
    backend = "faiss"

    def __init__(self):
        super().__init__()
        import faiss
        self._faiss = faiss
        self.embed, self.embed_info = _make_embedding()
        self.index = None

    def build_documents(self, docs):
        self.chunks, self.sources = _chunk_documents(_normalize_docs(docs))
        vecs = self.embed.encode(self.chunks)
        self.index = self._faiss.IndexFlatIP(vecs.shape[1])
        self.index.add(vecs)
        return self

    def _search(self, query, top_k=4):
        if not self.chunks or self.index is None:
            return []
        q = self.embed.encode([query])
        scores, idx = self.index.search(q, min(top_k, len(self.chunks)))
        return self._format(list(idx[0]), list(scores[0]))


class PineconeRetriever(_BaseRetriever):
    backend = "pinecone"

    def __init__(self, api_key: str, index_name: str):
        super().__init__()
        from pinecone import Pinecone
        self.embed, self.embed_info = _make_embedding()
        self._pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.namespace = "proposalforge"
        self._dim = self.embed.dim
        self._ensure_index()

    def _ensure_index(self):
        from pinecone import ServerlessSpec
        existing = [i["name"] for i in self._pc.list_indexes()]
        if self.index_name not in existing:
            self._pc.create_index(
                name=self.index_name, dimension=self._dim, metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        self.index = self._pc.Index(self.index_name)

    def build_documents(self, docs):
        docs = _normalize_docs(docs)
        self.chunks, self.sources = _chunk_documents(docs)
        vecs = self.embed.encode(self.chunks)
        self.namespace = "doc-" + "-".join(d["id"] for d in docs)[:40]
        vectors = [
            {"id": f"c-{i}", "values": vecs[i].tolist(),
             "metadata": {"text": self.chunks[i], "source": self.sources[i]}}
            for i in range(len(self.chunks))
        ]
        for start in range(0, len(vectors), 100):
            self.index.upsert(vectors=vectors[start:start + 100], namespace=self.namespace)
        return self

    def _search(self, query, top_k=4):
        if not self.chunks:
            return []
        q = self.embed.encode([query])[0].tolist()
        res = self.index.query(vector=q, top_k=top_k, include_metadata=True,
                               namespace=self.namespace)
        return [{"text": m["metadata"]["text"], "score": float(m["score"]),
                 "source": m["metadata"].get("source", "document")}
                for m in res.get("matches", [])]


class QdrantRetriever(_BaseRetriever):
    """Open-source vector DB (Qdrant). Free, self-hostable, production-grade.

    Uses QDRANT_URL when set, otherwise an in-process store (":memory:"), so it
    works in tests and demos without a running service.
    """
    backend = "qdrant"

    def __init__(self, url: str = None):
        super().__init__()
        from qdrant_client import QdrantClient
        self._models = __import__("qdrant_client.models", fromlist=["models"])
        self.embed, self.embed_info = _make_embedding()
        url = url or os.getenv("QDRANT_URL", "").strip()
        self.client = QdrantClient(url=url) if url else QdrantClient(":memory:")
        self.collection = os.getenv("QDRANT_COLLECTION", "proposalforge")

    def build_documents(self, docs):
        m = self._models
        self.chunks, self.sources = _chunk_documents(_normalize_docs(docs))
        vecs = self.embed.encode(self.chunks)
        dim = vecs.shape[1]
        try:
            self.client.delete_collection(self.collection)
        except Exception:
            pass
        self.client.create_collection(
            self.collection,
            vectors_config=m.VectorParams(size=dim, distance=m.Distance.COSINE))
        points = [m.PointStruct(id=i, vector=vecs[i].tolist(),
                                payload={"text": self.chunks[i], "source": self.sources[i]})
                  for i in range(len(self.chunks))]
        for start in range(0, len(points), 256):
            self.client.upsert(self.collection, points=points[start:start + 256])
        return self

    def _search(self, query, top_k=4):
        if not self.chunks:
            return []
        q = self.embed.encode([query])[0].tolist()
        hits = self.client.query_points(self.collection, query=q, limit=top_k).points
        return [{"text": h.payload["text"], "score": float(h.score),
                 "source": h.payload.get("source", "document")} for h in hits]


class PgVectorRetriever(_BaseRetriever):
    """PostgreSQL + pgvector backend. One engine for app data *and* vectors.

    Requires DATABASE_URL (postgresql://...) and the pgvector extension.
    """
    backend = "pgvector"

    def __init__(self, dsn: str = None):
        super().__init__()
        import psycopg2  # noqa: F401
        from pgvector.psycopg2 import register_vector
        self._psycopg2 = psycopg2
        self._register_vector = register_vector
        self.embed, self.embed_info = _make_embedding()
        self.dsn = dsn or os.getenv("DATABASE_URL")
        if not self.dsn:
            raise RuntimeError("DATABASE_URL required for pgvector backend")
        self.table = os.getenv("PGVECTOR_TABLE", "pf_chunks")
        self._conn = psycopg2.connect(self.dsn)
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self._conn.commit()
        register_vector(self._conn)

    def build_documents(self, docs):
        self.chunks, self.sources = _chunk_documents(_normalize_docs(docs))
        vecs = self.embed.encode(self.chunks)
        dim = vecs.shape[1]
        with self._conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {self.table}")
            cur.execute(f"CREATE TABLE {self.table} "
                        f"(id serial PRIMARY KEY, text text, source text, embedding vector({dim}))")
            for i in range(len(self.chunks)):
                cur.execute(f"INSERT INTO {self.table} (text, source, embedding) VALUES (%s,%s,%s)",
                            (self.chunks[i], self.sources[i], vecs[i].tolist()))
        self._conn.commit()
        return self

    def _search(self, query, top_k=4):
        if not self.chunks:
            return []
        q = self.embed.encode([query])[0].tolist()
        with self._conn.cursor() as cur:
            # cosine distance operator (<=>); similarity = 1 - distance
            cur.execute(f"SELECT text, source, 1 - (embedding <=> %s::vector) AS score "
                        f"FROM {self.table} ORDER BY embedding <=> %s::vector LIMIT %s",
                        (q, q, top_k))
            rows = cur.fetchall()
        return [{"text": r[0], "score": float(r[2]), "source": r[1] or "document"} for r in rows]


# --------------------------------------------------------------------- factory
def get_retriever() -> _BaseRetriever:
    choice = (os.getenv("VECTOR_BACKEND", "auto") or "auto").lower()
    pinecone_key = (os.getenv("PINECONE_API_KEY") or "").strip()
    pinecone_index = (os.getenv("PINECONE_INDEX", "proposalforge") or "").strip()

    def _try(make, name):
        try:
            return make()
        except Exception as e:
            print(f"{name} unavailable ({e}); falling back.")
            return None

    def _try_qdrant():
        return _try(lambda: QdrantRetriever(), "Qdrant")

    def _try_pgvector():
        return _try(lambda: PgVectorRetriever(), "pgvector")

    def _try_pinecone():
        if pinecone_key:
            return _try(lambda: PineconeRetriever(pinecone_key, pinecone_index), "Pinecone")
        return None

    def _try_faiss():
        return _try(lambda: FaissRetriever(), "FAISS")

    if choice == "qdrant":
        return _try_qdrant() or _try_faiss() or TfidfRetriever()
    if choice == "pgvector":
        return _try_pgvector() or _try_faiss() or TfidfRetriever()
    if choice == "pinecone":
        return _try_pinecone() or _try_faiss() or TfidfRetriever()
    if choice == "faiss":
        return _try_faiss() or TfidfRetriever()
    if choice == "tfidf":
        return TfidfRetriever()
    # auto: prefer managed/open vector DBs if configured, then local, then tfidf
    if os.getenv("QDRANT_URL"):
        return _try_qdrant() or _try_faiss() or TfidfRetriever()
    return _try_pinecone() or _try_faiss() or TfidfRetriever()
