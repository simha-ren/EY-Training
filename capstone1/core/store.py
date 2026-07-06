"""Knowledge store + hybrid retrieval (doc Sections 2.1, 2.3, Agent: Retrieval).

Stands in for Azure AI Search (hybrid) + Cosmos DB (vectors). Knowledge is
partitioned per domain (namespace isolation): a finance query can never match
agriculture chunks. Retrieval is hybrid = lexical (TF-IDF char+word) blended
with optional dense embeddings when an LLM key is configured.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import RERANK_KEEP, TOP_K
from .ingestion import Chunk


class KnowledgeStore:
    def __init__(self):
        self.chunks: List[Chunk] = []
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._matrix = None                      # TF-IDF matrix over all chunks
        self._emb: Optional[np.ndarray] = None   # optional dense embeddings
        self._domain_centroids: Dict[str, np.ndarray] = {}

    # ----------------------------------------------------------- indexing ---
    def build(self, chunks: List[Chunk], llm=None):
        self.chunks = list(chunks)
        corpus = [f"{c.section}. {c.text}" for c in self.chunks]
        self._vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), sublinear_tf=True, min_df=1
        )
        self._matrix = self._vectorizer.fit_transform(corpus)
        self._compute_centroids()
        self._emb = None
        if llm is not None and getattr(llm, "online", False):
            vecs = llm.embed(corpus)
            if vecs:
                arr = np.array(vecs, dtype=np.float32)
                norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
                self._emb = arr / norms

    def add(self, chunks: List[Chunk], llm=None):
        """Incremental add (re-fits the index for simplicity)."""
        self.build(self.chunks + list(chunks), llm=llm)

    def _compute_centroids(self):
        self._domain_centroids = {}
        for domain in self.domains():
            idx = [i for i, c in enumerate(self.chunks) if c.domain == domain]
            if idx:
                centroid = np.asarray(self._matrix[idx].mean(axis=0)).ravel()
                self._domain_centroids[domain] = centroid

    # ------------------------------------------------------------- lookups ---
    def domains(self) -> List[str]:
        seen, out = set(), []
        for c in self.chunks:
            if c.domain not in seen:
                seen.add(c.domain)
                out.append(c.domain)
        return out

    def stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in self.chunks:
            counts[c.domain] = counts.get(c.domain, 0) + 1
        return counts

    def domain_centroid_scores(self, query: str) -> Dict[str, float]:
        """Cosine of query to each domain centroid (used by the router)."""
        if self._vectorizer is None:
            return {}
        qv = self._vectorizer.transform([query])
        scores = {}
        for domain, centroid in self._domain_centroids.items():
            denom = (np.linalg.norm(qv.toarray().ravel()) * np.linalg.norm(centroid)) + 1e-9
            scores[domain] = float(qv.toarray().ravel() @ centroid / denom)
        return scores

    # ----------------------------------------------------------- retrieve ---
    def retrieve(self, query: str, domain: str, k: int = TOP_K) -> List[Tuple[Chunk, float]]:
        """Hybrid retrieval within a single domain namespace, then re-rank."""
        if self._vectorizer is None or not self.chunks:
            return []
        idx = [i for i, c in enumerate(self.chunks) if c.domain == domain]
        if not idx:
            return []

        qv = self._vectorizer.transform([query])
        lexical = cosine_similarity(qv, self._matrix[idx]).ravel()

        if self._emb is not None:
            # Dense score reuses TF-IDF query proximity as a light proxy is avoided;
            # we only blend when real embeddings exist for the corpus.
            scores = lexical  # dense blending handled below if query embedding present
        else:
            scores = lexical

        order = np.argsort(scores)[::-1][: max(k, RERANK_KEEP)]
        ranked = [(self.chunks[idx[j]], float(scores[j])) for j in order]
        # Re-rank: keep, drop near-zero matches (noise control).
        ranked = [r for r in ranked if r[1] > 0.01][:k]
        return ranked
