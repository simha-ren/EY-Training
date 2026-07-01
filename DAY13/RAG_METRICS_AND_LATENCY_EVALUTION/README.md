# Detailed RAG Metrics and Latency Evaluation Readme

This notebook provides a detailed evaluation of a Retrieval-Augmented Generation (RAG) system, focusing on key metrics like token count, latency, answer relevance, faithfulness, and context precision. The goal is to understand the performance and quality of the RAG pipeline.

## Architecture Overview

The RAG system implemented here follows a standard architecture, consisting of the following main components:

1.  **Articles (Knowledge Base)**: A collection of predefined `Article` objects, each containing a `title` and `content`. These articles serve as the knowledge base from which the RAG system retrieves information.

2.  **Embedder (`LocalHashingEmbedder`)**: This component is responsible for converting textual content (articles and queries) into numerical vector representations (embeddings). It uses `HashingVectorizer` from `sklearn` to create sparse, fixed-size vectors. These embeddings allow for efficient similarity comparisons.

    *   `embed_documents(texts)`: Embeds a list of text documents.
    *   `embed_query(query)`: Embeds a single query string.

3.  **Vector Store (Implicit)**: The embeddings of the articles are stored in memory as a NumPy array (`article_vectors`). This acts as a simple vector store for fast retrieval.

4.  **Retriever (`retrieve` function)**: When a query is made, this component performs a vector similarity search to find the most relevant articles from the knowledge base.

    *   It embeds the incoming query using the `LocalHashingEmbedder`.
    *   It calculates the cosine similarity between the query embedding and all article embeddings.
    *   It returns the `TOP_K` (configured as 3) most similar articles as `RetrievedChunk` objects, along with the embedding and retrieval latencies.

5.  **Generator (`generate_grounded_answer` function)**: This component constructs an answer based on the original query and the content of the retrieved chunks.

    *   It identifies key content words in the query.
    *   It selects sentences from the retrieved chunks that share common words with the query.
    *   If no such sentences are found, it defaults to the first sentence of the first retrieved chunk.
    *   It combines these selected sentences to form the final answer. A small, deterministic delay is introduced to simulate generation latency.

## Evaluation Pipeline

The `evaluate_query` function orchestrates the RAG process for each `QueryCase` and collects various performance and quality metrics:

1.  **Retrieval**: Calls the `retrieve` function to get relevant chunks and measure embedding and retrieval latency.
2.  **Generation**: Calls the `generate_grounded_answer` function to produce an answer and measure generation latency.
3.  **Metric Calculation**: Computes several metrics to assess the quality and efficiency of the RAG system.

    *   **Token Count**: Measures the number of tokens in the prompt (context + question) and the generated answer.
    *   **Latency**: Measures the time taken for embedding, retrieval, and answer generation.
    *   **Answer Relevance**: Quantifies how semantically similar the generated answer is to the original query.
    *   **Faithfulness**: Assesses what proportion of the terms in the generated answer are directly supported by the retrieved context.
    *   **Context Precision**: Determines the proportion of retrieved chunks that are actually relevant to the expected answer or query.

## Key Metrics Explained

*   **Token count**: This metric tracks the total number of words/tokens processed during a query, encompassing both the input prompt (query + retrieved context) and the generated output answer. A lower token count can indicate higher efficiency for systems with per-token billing.

*   **Latency**: This measures the time taken at various stages of the RAG pipeline, recorded in milliseconds:
    *   **Embedding latency**: Time to convert the user's query into a vector embedding.
    *   **Retrieval latency**: Time to search the vector store and retrieve relevant document chunks.
    *   **Generation latency**: Time for the language model (simulated here) to formulate an answer based on the query and retrieved context.
    *   **Total latency**: The sum of embedding, retrieval, and generation latencies.

*   **Answer relevance**: This metric quantifies how well the generated answer addresses the user's query. It's calculated using cosine similarity between the embeddings of the query and the generated answer. A score closer to 1 indicates higher relevance.

*   **Faithfulness**: This metric determines the extent to which the generated answer is grounded in the provided retrieved context. It measures the overlap of significant content words between the answer and the retrieved chunks. A score of 1 indicates that all content words in the answer are found in the context, minimizing hallucination.

*   **Context precision**: This metric assesses the quality of the retrieved chunks themselves. It measures the proportion of the retrieved chunks that are genuinely relevant to the query's expected answer. Relevance is determined by whether the chunk's title matches the `expected_title` or if there is significant word overlap with a `reference_answer`. A high context precision means the retriever is effectively finding useful information.

## Output

The script generates the following outputs in the `output/` directory:

*   **`rag_metrics_by_query.csv`**: A CSV file containing all computed metrics for each individual query case.
*   **`rag_metrics_by_query.json`**: A JSON file with the same data as the CSV, formatted for programmatic use.
*   **`rag_metrics_report.md`**: This markdown report, summarizing the average metrics and listing generated plots.
*   **`plots/` directory**: Contains various plots visualizing the results:
    *   **`all_queries_summary.png`**: A summary plot showing token count, total latency, and quality metrics across all queries.
    *   **`qX_metrics.png` (e.g., `q1_metrics.png`)**: Individual plots for each query, showing its token count, latency breakdown, and quality metrics.
