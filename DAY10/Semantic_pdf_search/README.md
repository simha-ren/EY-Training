# Semantic Search Engine for PDF Content

This notebook implements a hybrid semantic search engine designed to retrieve relevant information from PDF documents. It combines the strengths of keyword-based search (sparse retrieval) and meaning-based search (dense retrieval) to provide robust and accurate results.

## Table of Contents

1.  [Overview](#1-overview)
2.  [Setup](#2-setup)
3.  [PDF Text Extraction](#3-pdf-text-extraction)
4.  [Hybrid Search Engine Components](#4-hybrid-search-engine-components)
    *   [Sparse Search (BM25)](#sparse-search-bm25)
    *   [Dense Search (SentenceTransformer)](#dense-search-sentencetransformer)
    *   [Reciprocal Rank Fusion (RRF)](#reciprocal-rank-fusion-rrf)
5.  [Performing a Search](#5-performing-a-search)
6.  [Evaluation](#6-evaluation)
    *   [Ground Truth Dataset](#ground-truth-dataset)
    *   [Evaluation Metrics (MRR & NDCG)](#evaluation-metrics-mrr--ndcg)
    *   [Results](#results)

---

## 1. Overview

The goal of this project is to build an effective search engine for unstructured text data within PDF documents. It addresses the limitations of traditional keyword search by incorporating semantic understanding, allowing it to find relevant information even if exact keywords are not present. The hybrid approach uses Reciprocal Rank Fusion (RRF) to combine sparse (BM25) and dense (SentenceTransformer embeddings) search results, leveraging the strengths of both methods.

---

## 2. Setup

The notebook requires the following Python libraries:

*   `pypdf`: For extracting text content from PDF files.
*   `sentence-transformers`: For generating dense vector embeddings for semantic search.
*   `rank-bm25`: For implementing the BM25 keyword-based search algorithm.

These libraries are installed at the beginning of the notebook.

---

## 3. PDF Text Extraction

The first step involves extracting textual content from the target PDF document. The `extract_text_from_pdf` function reads a PDF file (e.g., `/content/12153_INTRODUCTION TO MOBILE PHONE.pdf`), processes each page, cleans the extracted text (removing excess whitespace), and stores each page's content as a separate document in a `corpus` list.

---

## 4. Hybrid Search Engine Components

The search engine consists of three main parts:

### Sparse Search (BM25)

*   **Algorithm**: BM25Okapi is used for keyword-based search.
*   **Process**: The `corpus` is tokenized, and an inverted index is built. Given a query, BM25 calculates relevance scores for documents based on keyword frequency and inverse document frequency.
*   **Function**: `sparse_search(query, top_n)` returns a list of `(doc_id, score)` tuples.

### Dense Search (SentenceTransformer)

*   **Model**: `all-MiniLM-L6-v2` SentenceTransformer is used to generate dense vector embeddings.
*   **Process**: Each document in the `corpus` is converted into a high-dimensional vector (embedding). For a given query, its embedding is computed, and cosine similarity is used to find documents with semantically similar embeddings.
*   **Function**: `dense_search(query, top_n)` returns a list of `(doc_id, score)` tuples based on cosine similarity.

### Reciprocal Rank Fusion (RRF)

*   **Purpose**: To effectively combine the ranked lists from both sparse and dense search engines into a single, more robust ranked list.
*   **Algorithm**: RRF assigns scores to each document based on its rank in each individual system. Documents that appear high in both rankings receive a significantly higher combined score.
*   **Function**: `reciprocal_rank_fusion(sparse_results, dense_results, k, top_n)` takes the results from sparse and dense searches and produces a fused ranking.

---

## 5. Performing a Search

The `hybrid_search_engine(query, top_n)` function orchestrates the entire process:

1.  It executes both `sparse_search` and `dense_search` to get initial results.
2.  It then uses `reciprocal_rank_fusion` to combine these results.
3.  Finally, it prints the top `n` ranked results, showing the rank, RRF score, source page (1-indexed), and a snippet of the content.

**Example Query**:
`query = "what is a mobile phone?"`
`hybrid_search_engine(query, top_n=5)`

---

## 6. Evaluation

To objectively measure the performance of the hybrid search engine, a ground truth dataset and standard evaluation metrics are employed.

### Ground Truth Dataset

A `ground_truth` dictionary is provided where each key is a search query and its value is a list of relevant 1-indexed page numbers from the PDF. Users can populate and customize this dataset to reflect their specific relevance judgments.

**Example Ground Truth**:
```python
ground_truth = {
    "What are the advantages of a basic phone?": [2],
    "mobile phone features": [1, 3, 4],
    "What is a Smartphone?": [3],
    "uses of mobile phone": [5]
}
```

### Evaluation Metrics (MRR & NDCG)

Two key metrics are used:

*   **Mean Reciprocal Rank (MRR)**: Measures how high the first relevant document appears in the search results. An MRR of 1.0 means the first relevant document was always ranked first.

    $	ext{MRR} = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{1}{\text{rank}_q}$

*   **Normalized Discounted Cumulative Gain (NDCG@k)**: Measures the overall quality of the ranking, considering both the relevance of documents and their positions within the top `k` results. Higher scores indicate better rankings.

    $	ext{NDCG}_p = \frac{	ext{DCG}_p}{	ext{IDCG}_p}$

Both `calculate_mrr` and `calculate_ndcg` functions are implemented to compute these scores.

### Results

After running the evaluation on the provided ground truth, the following scores were obtained:

*   **Mean Reciprocal Rank (MRR):** 0.7500
*   **Normalized Discounted Cumulative Gain (NDCG@5):** 0.7920

These results indicate good performance, with relevant documents generally ranking high in the search results.
