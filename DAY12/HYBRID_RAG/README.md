# Project README: Hybrid RAG + Long-Context with HuggingFace LLM

This Colab notebook demonstrates the construction, evaluation, and optimization of a Retrieval-Augmented Generation (RAG) pipeline. It compares a RAG approach with a full-context baseline using a HuggingFace `distilgpt2` model for generation and Azure AI Search for retrieval. Key aspects include hybrid retrieval quality, latency profiling, and extensions like confidence filtering and simulated streaming.

## Architecture

## Architecture Diagram

```mermaid
graph TD
    A[User/Application] --> B{Query}

    %% Embedding Step
    B --> C[HuggingFace Embeddings];

    %% Retrieval Step
    C --> D{Retrieval Step: Search Knowledge Base};

    D -- Hybrid (BM25 + Vector) --> E[Azure AI Search (Hybrid)];
    D -- Vector-only --> F[FAISS (Vector Store)];

    E --> G{Context and Sources};
    F --> G;

    %% Confidence Filter Extension
    G -- L2 Distance --> H{Confidence Filter (FAISS)};
    H -- Block Low Confidence --> A;
    H -- Pass High Confidence --> I{LLM Generation};

    %% LLM Generation Step
    I[HuggingFacePipeline (distilgpt2)] --> J{Generated Answer};

    %% Streaming Extension (Simulated)
    J --> K[Simulated Streaming Output];

    K --> L[Display Answer to User];

    %% Key Components and Notes
    subgraph Key Components
        C -- model_name: all-MiniLM-L6-v2 --> C;
        E -- Index: simha-rag --> E;
        F -- In-memory vector store --> F;
        I -- causal LM --> I;
    end

    subgraph Pipeline Flow
        A -- Input Query --> B;
        B -- Process --> C;
        C -- Embed Query --> D;
        D -- Retrieve Context --> G;
        G -- Filter Context --> H;
        H -- Generate Response --> I;
        I -- Stream Output --> K;
        K -- User Experience --> L;
    end

    style A fill:#D4EDDA,stroke:#28A745,stroke-width:2px
    style L fill:#D4EDDA,stroke:#28A745,stroke-width:2px
    style C fill:#E0F7FA,stroke:#00BCD4,stroke-width:1px
    style E fill:#E0F7FA,stroke:#00BCD4,stroke-width:1px
    style F fill:#E0F7FA,stroke:#00BCD4,stroke-width:1px
    style I fill:#FFF3E0,stroke:#FF9800,stroke-width:1px
    style H fill:#FFECB3,stroke:#FFC107,stroke-width:1px
    style K fill:#FFE0B2,stroke:#FF9800,stroke-width:1px,stroke-dasharray: 5 5

```


## Table of Contents
1.  [Overview](#overview)
2.  [Setup](#setup)
3.  [Running the Notebook](#running-the-notebook)
4.  [Key Findings & Discussion](#key-findings--discussion)
5.  [Extensions](#extensions)

## Overview
This project focuses on building and evaluating a RAG pipeline in Google Colab. The main components are:
*   **Embeddings:** Local `HuggingFaceEmbeddings` using `all-MiniLM-L6-v2`.
*   **Retrieval:** Azure AI Search for hybrid (BM25 + vector) retrieval, and FAISS for vector-only retrieval.
*   **Large Language Model (LLM):** `HuggingFacePipeline` with `distilgpt2` for text generation.
*   **Corpus:** 20 hardcoded article summaries on AI/ML and related tech topics.
*   **Evaluation:** A/B testing on 20 test questions to compare RAG and a full-context baseline across latency, cost, and input tokens.
*   **Optimizations/Extensions:** Latency waterfall analysis, confidence score filtering, and simulated streaming UX.

## Setup
To run this notebook, you need to install dependencies and configure API keys.

### 1. Install Dependencies
Execute the initial cells to install necessary Python packages:
```bash
!pip install -q \
    langchain \
    langchain-openai \
    langchain-anthropic \
    langchain-community \
    langchain-core \
    langchain-text-splitters \
    langchain-groq \
    faiss-cpu==1.11.0 \
    anthropic==0.109.0 \
    azure-search-documents==11.6.0b12 \
    azure-identity \
    numpy pandas matplotlib tqdm
!pip install -q sentence-transformers
!pip install -q transformers
!pip install -q ngrok # Optional, for ngrok tunnel setup
```

### 2. API Keys & Configuration
Store your API keys in Colab secrets (click the '🔑' icon on the left panel) with the following names:
*   `AZURE_SEARCH_API_KEY`: Your Azure AI Search admin key.
*   `GROQ_API_KEY`: (If you intend to switch back to Groq) Your Groq API key.
*   `ANTHROPIC_API_KEY`: (If you intend to switch back to Anthropic) Your Anthropic API key.
*   `NGROK_AUTH_TOKEN`: (Optional) For ngrok authentication.

Set the `AZURE_SEARCH_ENDPOINT` in cell `zR3jVYSyIsoH` to your Azure AI Search service URL.

**Note:** This notebook currently uses `distilgpt2` locally, so `ANTHROPIC_API_KEY` and `GROQ_API_KEY` are commented out, and token cost tracking is set to 0. `OPENAI_API_KEY` is not required as `HuggingFaceEmbeddings` are used.

### 3. Key Configuration Constants
Important constants defined in cell `zR3jVYSyIsoH`:
*   `EMBEDDING_MODEL`: `"all-MiniLM-L6-v2"`
*   `EMBEDDING_DIM`: `384`
*   `CLAUDE_MODEL`: `"distilgpt2"`
*   `TOP_K`: `5`
*   `COST_INPUT`, `COST_OUTPUT`: Hypothetical costs for external LLMs.

## Running the Notebook
Execute the cells sequentially from top to bottom.

*   **Corpus Setup:** Loads 20 hardcoded article summaries, chunks them, and embeds them using `all-MiniLM-L6-v2`.
*   **Step 01 - Build RAG Pipeline:**
    *   Initializes Azure AI Search client and creates a hybrid index.
    *   Uploads the embedded chunks to Azure AI Search.
    *   Sets up FAISS for vector-only retrieval.
    *   Configures `HuggingFacePipeline` with `distilgpt2` for generation.
    *   Defines the `rag_answer` function, an instrumented RAG pipeline combining embedding, hybrid retrieval, and generation.
*   **Step 02 - Hybrid Retrieval Quality (MRR@5):** Evaluates vector-only (FAISS) vs. hybrid (Azure AI Search) retrieval using MRR@5 on a test set.
*   **Step 03 - Full Context Baseline:**
    *   Prepares a full-context string by concatenating the first 50 chunks.
    *   Defines `full_context_answer` to stuff the entire (truncated) corpus into the LLM's context.
*   **Step 04 - A/B Evaluation (20 Questions):** Runs both RAG and full-context pipelines on 20 test questions, measuring latency, cost, and input tokens.
*   **Step 05 - Latency Profiler (Waterfall Breakdown):** Breaks down the RAG pipeline latency into embed, retrieve, and generate stages to identify bottlenecks.

## Key Findings & Discussion

### 1. Latency Bottleneck
*   **Observation:** The **Generate** stage dominates the RAG pipeline latency, accounting for approximately **73.2%** of the total time (953.4ms out of 1301.6ms on average) as seen in the "RAG Pipeline Latency Waterfall" plot.
*   **Implication for Optimization:** Future optimization efforts should primarily target reducing LLM generation time (e.g., using a faster/smaller LLM, optimizing inference, or employing techniques like speculative decoding).

### 2. Cost at Scale
*   **Current State:** Due to the use of a local `distilgpt2` model, the reported cost is $0.00000 per query for both RAG and full-context.
*   **Hypothetical for External LLM (e.g., Claude):** If using an external LLM with `COST_INPUT = $3e-6` and `COST_OUTPUT = $15e-6`:
    *   **RAG:** Estimated monthly cost of ~$86,850 at 1 million queries/day.
    *   **Full Context:** Estimated monthly cost of ~$280,260 at 1 million queries/day.
*   **Conclusion:** The full-context approach would be significantly more expensive due to the larger amount of input tokens processed per query, highlighting RAG's cost efficiency.

### 3. Hybrid vs. Vector-only Retrieval
*   **Observation:** Hybrid retrieval (Azure AI Search with BM25+vector) achieved an MRR@5 of 0.933, outperforming vector-only (FAISS) at 0.875.
*   **Queries Benefiting Most:** Queries containing specific acronyms and technical terms, such as "How does BERT use self-attention for NLP tasks?" (where Hybrid achieved MRR 1.00 vs. Vector-only 0.50), significantly benefited from BM25's keyword matching capabilities. This demonstrates how hybrid approaches can bridge the gap between semantic and lexical search.

### 4. Confidence Thresholding
*   **L2 Distance Distribution:** The histogram shows a distribution of L2 distances, where lower values indicate higher relevance.
*   **Medical Assistant vs. Casual Chatbot:**
    *   **Medical Assistant:** Would require a **lower L2_THRESHOLD (e.g., 0.7-0.8)** to prioritize extreme accuracy and minimize the risk of incorrect information, even if it means blocking more queries.
    *   **Casual Chatbot:** Could use a **higher L2_THRESHOLD (e.g., 1.1-1.2)** to ensure a broader range of questions are answered, accepting a slightly lower degree of relevance for increased user engagement.

## Extensions

### Streaming Responses
*   The notebook demonstrates a simulated streaming experience for the local `distilgpt2` model, showing the importance of Time-to-First-Token (TTFT) for perceived responsiveness.
*   **Production Architecture:** A production system would integrate native LLM streaming APIs (e.g., SSE, WebSockets), implement asynchronous backend processing, chunk responses efficiently, and progressively render on the frontend to optimize TTFT.

### Confidence Score Filter
*   The `rag_with_confidence` function uses the FAISS L2 distance to block answers when the best retrieved chunk is not relevant enough (L2 distance exceeds a predefined `L2_THRESHOLD`). This mechanism is crucial for controlling the quality and trustworthiness of RAG outputs.
