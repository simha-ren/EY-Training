# Day 12 - Colab 1: Indexing & Multi-DB Retrieval Showdown

## Table of Contents

1.  [Introduction](#introduction)
2.  [Setup and Configuration](#setup-and-configuration)
3.  [Core Functionalities](#core-functionalities)
    *   [Local Hashing Embedder](#local-hashing-embedder)
    *   [Document Loading and Embedding](#document-loading-and-embedding)
    *   [Benchmarking Search (FAISS, Pinecone, Azure AI Search)](#benchmarking-search-faiss-pinecone-azure-ai-search)
    *   [Cohere Reranking](#cohere-reranking)
    *   [Performance Summary and Plotting](#performance-summary-and-plotting)
4.  [Usage](#usage)
5.  [Interpreting Results](#interpreting-results)
6.  [Further Exploration](#further-exploration)

## Introduction

This Colab notebook provides a comprehensive benchmark for various vector database and retrieval methods, including **FAISS**, **Pinecone**, and **Azure AI Search**. Additionally, it integrates **Cohere's Rerank API** to demonstrate its impact on retrieval effectiveness. The primary goal is to compare the latency and relevance (Hit@K, MRR) of these systems for a given set of hardcoded articles and benchmark queries.

## Setup and Configuration

Before running the notebook, ensure all necessary libraries are installed and API keys are configured.

### 1. Install Dependencies

The first code cell handles the installation of all required Python packages:

```python
!{sys.executable} -m pip uninstall -y pinecone-client # Ensure correct pinecone client
!{sys.executable} -m pip install -q \
    langchain-core \
    langchain-text-splitters \
    faiss-cpu \
    tqdm \
    scikit-learn \
    pinecone \
    azure-search-documents \
    azure-core \
    cohere
```

### 2. API Key Configuration

API keys for services like Pinecone, Azure AI Search, Groq, and Cohere are loaded from Colab's secret manager. You *must* set these in your Colab environment under the '🔑' icon in the left panel. Create secrets with the following names:

*   `GROQ_API_KEY`
*   `PINECONE_API_KEY`
*   `AZURE_SEARCH_API_KEY`
*   `COHERE_API_KEY`

Other configuration parameters like `LOCAL_EMBEDDING_DIM`, `PINECONE_INDEX_NAME`, `AZURE_SEARCH_ENDPOINT`, `COHERE_RERANK_MODEL`, etc., are defined in the `Configuration` section and can be modified there. Default values are provided for non-sensitive parameters.

## Core Functionalities

### Local Hashing Embedder

The notebook uses a `LocalHashingEmbedder` based on `HashingVectorizer` from `scikit-learn` for generating document and query embeddings. This ensures that the vectorization process is consistent and local, allowing for focused benchmarking of the vector databases themselves.

### Document Loading and Embedding

A corpus of Wikipedia-style articles (both hardcoded and benchmark-specific) is loaded and split into chunks using `RecursiveCharacterTextSplitter`. These chunks are then embedded using the `LocalHashingEmbedder`.

### Benchmarking Search (FAISS, Pinecone, Azure AI Search)

The `benchmark_search` function orchestrates the evaluation for each vector database:

*   **FAISS**: An in-memory, exact k-NN search using `faiss.IndexFlatL2`.
*   **Pinecone**: A serverless cosine vector search, interacting with a Pinecone index (created if it doesn't exist, with upsertion of embedded documents).
*   **Azure AI Search**: A hybrid BM25 plus vector search, utilizing Azure's capabilities for index creation, document upload, and querying.

Each benchmark measures query latencies (p50, p95, mean) and `Hit@K` (whether the expected title is in the top `K` results).

### Cohere Reranking

If a `COHERE_API_KEY` is provided, the `run_cohere_rerank` function performs a reranking comparison. It first retrieves `rerank_top_k` documents using FAISS, then applies Cohere's `rerank-english-v3.0` model to reorder these results. It calculates the Mean Reciprocal Rank (MRR@10) both *before* and *after* reranking to assess the improvement in relevance.

### Performance Summary and Plotting

After all benchmarks are complete:

*   `print_summary` displays a tabular overview of p50, p95, mean latency, and `Hit@K` for each vector database.
*   `save_latency_plot` generates a bar chart visualizing the p50 and p95 latencies across the different systems, saving it as `latency_benchmark.png`.

## Usage

The notebook can be run by executing all cells sequentially. The `main` function (in cell `Hkr4r9q_SgAk`) processes command-line arguments to control the execution flow:

*   `--max-chunks`: Maximum hardcoded corpus chunks to index (default: 500).
*   `--skip-pinecone`: Skip Pinecone benchmark even if keys are set.
*   `--skip-azure`: Skip Azure AI Search benchmark even if keys are set.
*   `--skip-rerank`: Skip Cohere rerank even if `COHERE_API_KEY` is set.
*   `--skip-plot`: Skip matplotlib chart generation.

In a Colab environment, these arguments are typically set programmatically within the notebook or passed via `sys.argv` manipulation.

## Interpreting Results

*   **Latency (p50, p95, Mean ms)**: Lower values indicate faster query response times. Expect local solutions like FAISS to be significantly faster than cloud services due to network overhead.
*   **Hit@K**: A value closer to 1.0 indicates higher relevance, meaning the correct answer is consistently found within the top `K` results.
*   **MRR@10 (Cohere Rerank)**: A higher MRR@10 value (especially `After RR`) indicates better reranking performance. A positive `delta` suggests that Cohere reranking improved the average reciprocal rank of the relevant document.

## Further Exploration

*   **Adjust `TOP_K`**: Experiment with different `TOP_K` values for search and `rerank_top_k` for Cohere.
*   **Different Embedders**: Integrate other embedding models (e.g., from OpenAI, Google, Sentence Transformers) to see their impact on retrieval quality.
*   **Larger Corpus**: Test with a larger and more diverse document corpus.
*   **Advanced FAISS Indexes**: Explore more advanced FAISS index types (e.g., `IndexIVFFlat`, `IndexHNSWFlat`) for speed-accuracy tradeoffs.
*   **Semantic Reranking**: Investigate how Cohere's reranking impacts scenarios where initial retrieval is less precise.

## OUTPUT:

https://github.com/simha-ren/EY-Training/blob/main/DAY12/INDEXING%20%26%20MULTI-DB%20RETRIEVAL/latency_benchmark.png
