# Hybrid Semantic Search Engine Evaluation

This notebook demonstrates and evaluates a hybrid search engine that combines sparse (keyword-based) and dense (semantic-based) retrieval methods using Reciprocal Rank Fusion (RRF).

## Project Goal

The primary goal of this project is to build and evaluate a robust search engine capable of handling diverse user queries by leveraging the strengths of both traditional keyword matching and modern semantic understanding.

## Components

1.  **Corpus**: A small, sample corporate/tech dataset of 6 technical documents.
2.  **Sparse Search (BM25)**: Implemented using the `rank_bm25` library for keyword-based retrieval.
3.  **Dense Search (Sentence Transformers)**: Utilizes the `all-MiniLM-L6-v2` model from `sentence-transformers` to generate document and query embeddings for semantic similarity search.
4.  **Reciprocal Rank Fusion (RRF)**: A method to combine the rankings from both sparse and dense search engines to produce a more robust and comprehensive final ranking.
5.  **Evaluation Metrics**: Mean Reciprocal Rank (MRR) and Normalized Discounted Cumulative Gain (NDCG@5) are used to quantitatively assess the search engine's performance.

## Setup and Usage

First, install the necessary libraries:

```bash
!pip install -q sentence-transformers rank-bm25
```

The notebook then proceeds with:

*   Loading the sample `corpus`.
*   Initializing and testing `sparse_search` (BM25).
*   Initializing and testing `dense_search` (Sentence Transformers).
*   Defining the `reciprocal_rank_fusion` function.
*   Defining the `hybrid_search_engine` function, which orchestrates the above components.

## Ground Truth Dataset

To evaluate the search engine, a `ground_truth` dataset was manually created. This dataset maps specific queries to a list of relevant document IDs from the `corpus`.

```python
ground_truth = {
    "Apple mobile device issues": [1, 0],
    "Macbook laptop battery optimization": [5, 4],
    "frozen iPhone": [0],
    "camera system": [2]
}
```

## Evaluation Metrics Implementation

Functions `calculate_mrr` and `calculate_ndcg` were implemented to compute the respective metrics based on the `ground_truth` and the output of the `hybrid_search_engine`.

## Performance Results

After running the evaluation, the following scores were obtained:

*   **Mean Reciprocal Rank (MRR):** `1.0000`
*   **Normalized Discounted Cumulative Gain (NDCG@5):** `0.9693`

### Interpretation of Results

*   An **MRR of 1.0000** indicates that for every query in the `ground_truth` dataset, the first relevant document was always ranked at the very top (rank 1) by the `hybrid_search_engine`.
*   An **NDCG@5 of 0.9693** suggests a very high-quality ranking, where highly relevant documents are consistently placed at the top of the search results within the top 5 positions, closely matching an ideal ranking.

## OUTPUT :
https://github.com/simha-ren/EY-Training/blob/main/DAY10/Semantic_search/semantic_1.PNG

https://github.com/simha-ren/EY-Training/blob/main/DAY10/Semantic_search/Semantic_2.PNG

These results demonstrate that the hybrid search engine, when evaluated against this specific ground truth, performs exceptionally well.
